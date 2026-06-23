"""Cross-process single-flight lock for heavy ML work (D36).

`pipeline_group_lock` is a one-row-per-group advisory lock in Postgres. The row's
PK is the group name, so INSERT uniqueness = race-free acquisition; `locked_at`
doubles as a lease heartbeat (D30). The daemon and every one-shot CLI ML step
share these primitives so that — on a GPU-less host where two native inference
runtimes in flight at once segfault and oversubscribe the CPU — only one heavy ML
job runs system-wide at any time.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from core.config import settings
from core.db import get_session
from core.models import PipelineGroupLock
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

GROUP_CLUSTER_LABEL_SCORE = "cluster_label_score"
GROUP_ANALYSIS = "analysis"


class LockHeld(Exception):
    """Raised when a single-flight lock is already held by another process."""

    def __init__(self, group: str) -> None:
        super().__init__(f"pipeline group lock '{group}' already held")
        self.group = group


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _lease_cutoff() -> datetime:
    return _now() - timedelta(seconds=settings.pipeline_lock_lease_ttl_seconds)


async def reap_expired_lock(group: str) -> None:
    async with get_session() as session:
        await session.execute(
            delete(PipelineGroupLock).where(
                PipelineGroupLock.group_name == group,
                PipelineGroupLock.locked_at < _lease_cutoff(),
            )
        )
        await session.commit()


async def acquire_lock(group: str) -> bool:
    await reap_expired_lock(group)
    async with get_session() as session:
        try:
            session.add(PipelineGroupLock(group_name=group))
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            logger.warning("group=%s lock already held (fresh lease), skipping", group)
            return False


async def release_lock(group: str) -> None:
    async with get_session() as session:
        await session.execute(
            delete(PipelineGroupLock).where(PipelineGroupLock.group_name == group)
        )
        await session.commit()


async def bump_lock(group: str) -> None:
    async with get_session() as session:
        await session.execute(
            update(PipelineGroupLock)
            .where(PipelineGroupLock.group_name == group)
            .values(locked_at=_now())
        )
        await session.commit()


async def is_lock_held(group: str) -> bool:
    """True if a non-expired lease row exists for the group (held by any process)."""
    async with get_session() as session:
        locked_at = (
            await session.execute(
                select(PipelineGroupLock.locked_at).where(
                    PipelineGroupLock.group_name == group
                )
            )
        ).scalar_one_or_none()
    return locked_at is not None and locked_at >= _lease_cutoff()


async def _heartbeat(group: str, stop: asyncio.Event) -> None:
    interval = settings.pipeline_lock_heartbeat_seconds
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except TimeoutError:
            pass
        try:
            await bump_lock(group)
        except Exception:
            logger.exception("lock heartbeat bump failed group=%s", group)


@contextlib.asynccontextmanager
async def hold_lock(group: str) -> AsyncIterator[None]:
    """Hold a single-flight lock for the duration of the block, with a background
    heartbeat so a long-running (multi-minute) ML step keeps its lease fresh.

    Raises LockHeld immediately if another process holds a fresh lease — callers
    (one-shot CLI ML steps) should catch it and exit instead of running
    concurrently with the daemon or another manual run.
    """
    if not await acquire_lock(group):
        raise LockHeld(group)
    stop = asyncio.Event()
    hb = asyncio.create_task(_heartbeat(group, stop))
    try:
        yield
    finally:
        stop.set()
        with contextlib.suppress(asyncio.CancelledError):
            await hb
        await release_lock(group)
