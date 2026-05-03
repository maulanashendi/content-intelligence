import asyncio
import contextlib
import logging
import random
import signal
from collections.abc import Callable, Coroutine
from typing import Any

import asyncpg
from core.config import settings
from core.db import get_session
from core.models import PipelineGroupLock
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

RECONNECT_BACKOFF_BASE = 10

_GROUP_INGEST_EMBED = "ingest_embed"
_GROUP_CLUSTER_LABEL_SCORE = "cluster_label_score"
_GROUP_EMBED_ONLY = "embed_only"

_CHANNEL_TO_GROUP = {
    "pipeline_ingest_embed_requested": _GROUP_INGEST_EMBED,
    "pipeline_cluster_label_score_requested": _GROUP_CLUSTER_LABEL_SCORE,
    "pipeline_embed_requested": _GROUP_EMBED_ONLY,
}


async def _run_ingest_embed() -> None:
    from ingest.pipeline import run as ingest_run

    await ingest_run()

    from embedding.pipeline import run as embed_run

    await embed_run()


async def _run_cluster_label_score() -> None:
    from clustering.pipeline import run as cluster_run

    await cluster_run()

    from labeling.pipeline import run as label_run

    await label_run()

    from scoring.pipeline import run as score_run

    await score_run()


async def _run_embed_only() -> None:
    from embedding.pipeline import run as embed_run

    await embed_run()


_GROUP_RUNNERS: dict[str, Callable[[], Coroutine[Any, Any, None]]] = {
    _GROUP_INGEST_EMBED: _run_ingest_embed,
    _GROUP_CLUSTER_LABEL_SCORE: _run_cluster_label_score,
    _GROUP_EMBED_ONLY: _run_embed_only,
}


async def _acquire_lock(group: str) -> bool:
    async with get_session() as session:
        try:
            session.add(PipelineGroupLock(group_name=group))
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            logger.warning("group=%s lock already held, skipping trigger", group)
            return False


async def _release_lock(group: str) -> None:
    async with get_session() as session:
        await session.execute(
            delete(PipelineGroupLock).where(PipelineGroupLock.group_name == group)
        )
        await session.commit()


async def _worker(group: str, queue: asyncio.Queue[None], shutdown: asyncio.Event) -> None:
    runner = _GROUP_RUNNERS[group]
    while not shutdown.is_set():
        try:
            await asyncio.wait_for(queue.get(), timeout=1.0)
        except TimeoutError:
            continue

        if not await _acquire_lock(group):
            continue

        logger.info("pipeline group=%s started", group)
        try:
            await runner()
            logger.info("pipeline group=%s finished", group)
        except Exception:
            logger.exception("pipeline group=%s failed", group)
        finally:
            await _release_lock(group)


async def _listen(shutdown: asyncio.Event, queues: dict[str, asyncio.Queue[None]]) -> None:
    def _on_notify(conn: Any, pid: int, channel: str, payload: str) -> None:
        group = _CHANNEL_TO_GROUP.get(channel)
        if group is None:
            return
        q = queues[group]
        if q.full():
            logger.warning("queue full for group=%s, trigger dropped", group)
            return
        q.put_nowait(None)

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    while not shutdown.is_set():
        conn = None
        try:
            conn = await asyncpg.connect(dsn=dsn)
            for channel in _CHANNEL_TO_GROUP:
                await conn.add_listener(channel, _on_notify)
            logger.info("pg_notify listener attached channels=%s", list(_CHANNEL_TO_GROUP))
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
    shutdown = asyncio.Event()
    _install_signal_handlers(shutdown)

    queues: dict[str, asyncio.Queue[None]] = {
        _GROUP_INGEST_EMBED: asyncio.Queue(maxsize=1),
        _GROUP_CLUSTER_LABEL_SCORE: asyncio.Queue(maxsize=1),
        _GROUP_EMBED_ONLY: asyncio.Queue(maxsize=1),
    }

    logger.info("pipeline serve daemon started")

    listener_task = asyncio.create_task(_listen(shutdown, queues))
    worker_tasks = [
        asyncio.create_task(_worker(group, queues[group], shutdown)) for group in _GROUP_RUNNERS
    ]

    try:
        await shutdown.wait()
    finally:
        listener_task.cancel()
        for w in worker_tasks:
            w.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener_task
        for w in worker_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await w
        logger.info("pipeline serve daemon stopped")
