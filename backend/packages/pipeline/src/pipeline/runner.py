import asyncio
import contextlib
import logging
import random
import signal
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg
from core.config import settings
from core.db import get_session
from core.models import ClusterRun, ContentSource, PipelineGroupLock, SourceStatus
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

POLL_INTERVAL = 600
RECONNECT_BACKOFF_BASE = 10
IMMEDIATE_QUEUE_MAX = 1024

_GROUP_CLUSTER_LABEL_SCORE = "cluster_label_score"
_GROUP_ANALYSIS = "analysis"
_CHANNEL_RSS_SOURCE_CREATED = "rss_source_created"
_CHANNEL_CLUSTER_LABEL_SCORE = "pipeline_cluster_label_score_requested"
_CHANNEL_ANALYSIS = "pipeline_analysis_requested"

# Groups currently held by this process — used by the heartbeat task.
# Written/discarded on the loop (single-threaded coroutines) — no lock needed.
_held_groups: set[str] = set()


async def _run_ingest_then_embed() -> None:
    from ingest.pipeline import run as ingest_run

    await ingest_run()

    from ingest.scraper import run as scrape_run

    await scrape_run()

    from embedding.pipeline import run as embed_run

    await embed_run()


async def _fetch_one_source(source_id: UUID) -> None:
    from ingest.rss import (
        BlockedError,
        _set_source_status,
        fetch_and_store_source,
        make_http_client,
    )

    async with get_session() as session:
        source = await session.get(ContentSource, source_id)
        if source is None or not source.is_enabled:
            return
        sid, surl, sname = source.id, source.url, source.name

    async with make_http_client() as client:
        try:
            count = await fetch_and_store_source(client, sid, surl, sname)
            logger.info("immediate source=%s ingested %d articles", sname, count)
        except BlockedError:
            logger.warning("immediate source=%s blocked by provider", sname)
            await _set_source_status(sid, SourceStatus.blocked)
        except Exception:
            logger.exception("immediate source=%s fetch failed", sname)
            await _set_source_status(sid, SourceStatus.error)


def _enqueue_immediate(immediate: deque[str], payload: str) -> None:
    if len(immediate) == IMMEDIATE_QUEUE_MAX:
        dropped = immediate[0]
        logger.warning("immediate queue full, dropping oldest payload=%s", dropped)
    immediate.append(payload)


async def _ingest_loop(shutdown: asyncio.Event, immediate: deque[str]) -> None:
    loop = asyncio.get_running_loop()
    while not shutdown.is_set():
        try:
            await _run_ingest_then_embed()
        except Exception:
            logger.exception("ingest+embed cycle failed")

        deadline = loop.time() + POLL_INTERVAL
        while loop.time() < deadline and not shutdown.is_set():
            if immediate:
                payload = immediate.popleft()
                try:
                    sid = UUID(payload)
                except ValueError:
                    logger.warning("invalid UUID in notify payload: %s", payload)
                    continue
                asyncio.create_task(_fetch_one_source(sid))
                continue
            remaining = deadline - loop.time()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(shutdown.wait(), timeout=min(1.0, remaining))


async def _run_gsc_fetch() -> None:
    from ingest import gsc

    async with get_session() as session:
        await gsc.run(session, settings)


async def _run_cluster_label_score() -> None:
    from pipeline.cluster_label_score import run

    await run()


async def _run_analysis() -> None:
    from labeling.analysis import run as analysis_run

    await analysis_run()


def _lease_cutoff() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(
        seconds=settings.pipeline_lock_lease_ttl_seconds
    )


async def _reap_expired_lock(group: str) -> None:
    async with get_session() as session:
        await session.execute(
            delete(PipelineGroupLock).where(
                PipelineGroupLock.group_name == group,
                PipelineGroupLock.locked_at < _lease_cutoff(),
            )
        )
        await session.commit()


async def _acquire_lock(group: str) -> bool:
    await _reap_expired_lock(group)
    async with get_session() as session:
        try:
            session.add(PipelineGroupLock(group_name=group))
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            logger.warning("group=%s lock already held (fresh lease), skipping", group)
            return False


async def _release_lock(group: str) -> None:
    async with get_session() as session:
        await session.execute(
            delete(PipelineGroupLock).where(PipelineGroupLock.group_name == group)
        )
        await session.commit()


async def _heartbeat(shutdown: asyncio.Event, held: set[str]) -> None:
    interval = settings.pipeline_lock_heartbeat_seconds
    while not shutdown.is_set():
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=interval)
            return
        except TimeoutError:
            pass
        groups = list(held)
        if not groups:
            continue
        try:
            async with get_session() as session:
                await session.execute(
                    update(PipelineGroupLock)
                    .where(PipelineGroupLock.group_name.in_(groups))
                    .values(locked_at=datetime.now(UTC).replace(tzinfo=None))
                )
                await session.commit()
        except Exception:
            logger.exception("lock heartbeat bump failed groups=%s", groups)


async def _cluster_worker(
    queue: asyncio.Queue[None],
    shutdown: asyncio.Event,
    analysis_queue: asyncio.Queue[None],
) -> None:
    while not shutdown.is_set():
        try:
            await asyncio.wait_for(queue.get(), timeout=1.0)
        except TimeoutError:
            continue

        if not await _acquire_lock(_GROUP_CLUSTER_LABEL_SCORE):
            continue

        _held_groups.add(_GROUP_CLUSTER_LABEL_SCORE)
        logger.info("pipeline group=%s started", _GROUP_CLUSTER_LABEL_SCORE)
        try:
            await _run_gsc_fetch()
            await _run_cluster_label_score()
            logger.info("pipeline group=%s finished", _GROUP_CLUSTER_LABEL_SCORE)
            if not analysis_queue.full():
                analysis_queue.put_nowait(None)
                logger.info("analysis enqueued by cluster worker")
            else:
                logger.warning("analysis queue full, auto-enqueue skipped")
        except Exception:
            logger.exception("pipeline group=%s failed", _GROUP_CLUSTER_LABEL_SCORE)
        finally:
            _held_groups.discard(_GROUP_CLUSTER_LABEL_SCORE)
            await _release_lock(_GROUP_CLUSTER_LABEL_SCORE)


async def _analysis_worker(queue: asyncio.Queue[None], shutdown: asyncio.Event) -> None:
    while not shutdown.is_set():
        try:
            await asyncio.wait_for(queue.get(), timeout=1.0)
        except TimeoutError:
            continue

        if not await _acquire_lock(_GROUP_ANALYSIS):
            continue

        _held_groups.add(_GROUP_ANALYSIS)
        logger.info("pipeline group=%s started", _GROUP_ANALYSIS)
        try:
            await _run_analysis()
            logger.info("pipeline group=%s finished", _GROUP_ANALYSIS)
        except Exception:
            logger.exception("pipeline group=%s failed", _GROUP_ANALYSIS)
        finally:
            _held_groups.discard(_GROUP_ANALYSIS)
            await _release_lock(_GROUP_ANALYSIS)


def _next_run_at(now_utc: datetime, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    local_now = now_utc.astimezone(tz)
    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local_now:
        target += timedelta(days=1)
    return target.astimezone(UTC)


def _scheduled_boundary(now_utc: datetime, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    """Return the most recent scheduled boundary before now (naive UTC)."""
    local_now = now_utc.astimezone(tz)
    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target > local_now:
        target -= timedelta(days=1)
    return target.astimezone(UTC).replace(tzinfo=None)


async def _last_cluster_run_finished_at() -> datetime | None:
    async with get_session() as session:
        result = await session.execute(select(func.max(ClusterRun.finished_at)))
        return result.scalar_one_or_none()


async def _cluster_scheduler(shutdown: asyncio.Event, queue: asyncio.Queue[None]) -> None:
    tz = ZoneInfo(settings.timezone)
    poll = settings.cluster_scheduler_poll_seconds
    while not shutdown.is_set():
        now = datetime.now(UTC)
        boundary = _scheduled_boundary(
            now, settings.cluster_schedule_hour, settings.cluster_schedule_minute, tz
        )
        last_run = await _last_cluster_run_finished_at()

        should_fire = last_run is None or last_run < boundary
        if should_fire:
            if queue.full():
                logger.warning("cluster queue full at scheduled tick, dropping")
            else:
                queue.put_nowait(None)
                logger.info(
                    "cluster scheduler fired boundary=%s last_run=%s",
                    boundary.isoformat(),
                    last_run.isoformat() if last_run else "never",
                )
        else:
            next_run = _next_run_at(
                now, settings.cluster_schedule_hour, settings.cluster_schedule_minute, tz
            )
            logger.info(
                "cluster scheduler: next tick at %s (in %.0fs)",
                next_run.isoformat(),
                (next_run - now).total_seconds(),
            )

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(shutdown.wait(), timeout=poll)


async def _listen(
    shutdown: asyncio.Event,
    immediate: deque[str],
    cluster_queue: asyncio.Queue[None],
    analysis_queue: asyncio.Queue[None],
) -> None:
    def _on_source_created(conn: Any, pid: int, channel: str, payload: str) -> None:
        _enqueue_immediate(immediate, payload)

    def _on_cluster_requested(conn: Any, pid: int, channel: str, payload: str) -> None:
        if cluster_queue.full():
            logger.warning("cluster queue full, manual trigger dropped")
            return
        cluster_queue.put_nowait(None)

    def _on_analysis_requested(conn: Any, pid: int, channel: str, payload: str) -> None:
        if analysis_queue.full():
            logger.warning("analysis queue full, manual trigger dropped")
            return
        analysis_queue.put_nowait(None)

    handlers: dict[str, Any] = {
        _CHANNEL_RSS_SOURCE_CREATED: _on_source_created,
        _CHANNEL_CLUSTER_LABEL_SCORE: _on_cluster_requested,
        _CHANNEL_ANALYSIS: _on_analysis_requested,
    }

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    while not shutdown.is_set():
        conn = None
        try:
            conn = await asyncpg.connect(dsn=dsn)
            for channel, cb in handlers.items():
                await conn.add_listener(channel, cb)
            logger.info("pg_notify listener attached channels=%s", list(handlers))
            while not shutdown.is_set():
                await asyncio.sleep(300)
        except asyncio.CancelledError:
            return
        except Exception:
            backoff = RECONNECT_BACKOFF_BASE + random.uniform(0, RECONNECT_BACKOFF_BASE)
            logger.exception("listener connection lost, reconnecting in %.1fs", backoff)
            try:
                await asyncio.wait_for(shutdown.wait(), timeout=backoff)
                return
            except TimeoutError:
                pass
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    await conn.close()


def _install_signal_handlers(shutdown: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, shutdown.set)


async def run_loop() -> None:
    global _held_groups
    _held_groups = set()

    shutdown = asyncio.Event()
    _install_signal_handlers(shutdown)

    immediate: deque[str] = deque(maxlen=IMMEDIATE_QUEUE_MAX)
    cluster_queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
    analysis_queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)

    # Reap any lock rows left by a previous container that was SIGKILLed.
    for group in (_GROUP_CLUSTER_LABEL_SCORE, _GROUP_ANALYSIS):
        await _reap_expired_lock(group)
    logger.info("startup lock reap complete")

    logger.info(
        "pipeline daemon started poll_interval=%ds cluster_schedule=%02d:%02d %s",
        POLL_INTERVAL,
        settings.cluster_schedule_hour,
        settings.cluster_schedule_minute,
        settings.timezone,
    )

    from ingest.playwright_worker import run_loop as playwright_run_loop

    tasks = [
        asyncio.create_task(_listen(shutdown, immediate, cluster_queue, analysis_queue)),
        asyncio.create_task(_ingest_loop(shutdown, immediate)),
        asyncio.create_task(_cluster_scheduler(shutdown, cluster_queue)),
        asyncio.create_task(_cluster_worker(cluster_queue, shutdown, analysis_queue)),
        asyncio.create_task(playwright_run_loop(shutdown)),
        asyncio.create_task(_analysis_worker(analysis_queue, shutdown)),
        asyncio.create_task(_heartbeat(shutdown, _held_groups)),
    ]

    try:
        await shutdown.wait()
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await t
        logger.info("pipeline daemon stopped")
