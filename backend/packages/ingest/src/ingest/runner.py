import asyncio
import contextlib
import logging
import random
import signal
from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import httpx
from core.config import settings
from core.db import get_session
from core.models import ContentSource, SourceStatus, SourceType
from ingest.rss import BlockedError, _set_source_status, fetch_and_store_source
from sqlalchemy import select

logger = logging.getLogger(__name__)

POLL_INTERVAL = 600
BLOCK_DURATION = 3600
RECONNECT_BACKOFF_BASE = 10
IMMEDIATE_QUEUE_MAX = 1024

_blocked_until: dict[UUID, datetime] = {}
_immediate: deque[str] = deque(maxlen=IMMEDIATE_QUEUE_MAX)
_shutdown: asyncio.Event | None = None


def _is_blocked(source_id: UUID) -> bool:
    until = _blocked_until.get(source_id)
    if until is None:
        return False
    if datetime.now(UTC) >= until:
        del _blocked_until[source_id]
        return False
    return True


def _mark_blocked(source_id: UUID, source_name: str) -> None:
    unblock_at = datetime.now(UTC) + timedelta(seconds=BLOCK_DURATION)
    _blocked_until[source_id] = unblock_at
    logger.warning("source=%s blocked until %s", source_name, unblock_at.isoformat())


def _enqueue_immediate(payload: str) -> None:
    # deque(maxlen=N) drops the oldest entry on overflow; capture and log it.
    if len(_immediate) == IMMEDIATE_QUEUE_MAX:
        dropped = _immediate[0]
        logger.warning("immediate queue full, dropping oldest payload=%s", dropped)
    _immediate.append(payload)


async def _listen_for_new_sources() -> None:
    global _shutdown

    def _on_notify(conn, pid, channel, payload):
        _enqueue_immediate(payload)

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    if _shutdown is None:
        _shutdown = asyncio.Event()
    shutdown = _shutdown
    while not shutdown.is_set():
        conn = None
        try:
            conn = await asyncpg.connect(dsn=dsn)
            await conn.add_listener("rss_source_created", _on_notify)
            logger.info("pg_notify listener attached channel=rss_source_created")
            while not shutdown.is_set():
                await asyncio.sleep(300)
        except asyncio.CancelledError:
            return
        except Exception:
            backoff = RECONNECT_BACKOFF_BASE + random.uniform(0, RECONNECT_BACKOFF_BASE)
            logger.exception(
                "listener connection lost, reconnecting in %.1fs", backoff
            )
            try:
                await asyncio.wait_for(shutdown.wait(), timeout=backoff)
                return
            except asyncio.TimeoutError:
                pass
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    await conn.close()


async def _fetch_one_source(source_id: UUID) -> None:
    async with get_session() as session:
        source = await session.get(ContentSource, source_id)
        if source is None or not source.is_enabled:
            return
        sid, surl, sname = source.id, source.url, source.name

    if _is_blocked(sid):
        return

    timeout = httpx.Timeout(settings.ingest_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            count = await fetch_and_store_source(client, sid, surl, sname)
            logger.info("immediate source=%s ingested %d articles", sname, count)
        except BlockedError:
            _mark_blocked(sid, sname)
            await _set_source_status(sid, SourceStatus.blocked)
        except Exception:
            logger.exception("immediate source=%s fetch failed", sname)
            await _set_source_status(sid, SourceStatus.error)


async def _run_once() -> None:
    async with get_session() as session:
        result = await session.execute(
            select(ContentSource).where(
                ContentSource.source_type == SourceType.rss,
                ContentSource.is_enabled.is_(True),
            )
        )
        sources = [(s.id, s.url, s.name) for s in result.scalars()]

    active = [s for s in sources if not _is_blocked(s[0])]
    skipped = len(sources) - len(active)
    if skipped:
        logger.info("skipping %d blocked source(s)", skipped)

    timeout = httpx.Timeout(settings.ingest_timeout_seconds)

    async def _handle(source_id: UUID, source_url: str, source_name: str) -> None:
        try:
            count = await fetch_and_store_source(client, source_id, source_url, source_name)
            logger.info("source=%s ingested %d articles", source_name, count)
        except BlockedError:
            _mark_blocked(source_id, source_name)
        except Exception:
            logger.exception("source=%s fetch failed", source_name)

    async with httpx.AsyncClient(timeout=timeout) as client:
        await asyncio.gather(*[_handle(*s) for s in active])


def _install_signal_handlers(shutdown: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, shutdown.set)


async def run_loop() -> None:
    global _shutdown
    _shutdown = asyncio.Event()
    _immediate.clear()
    shutdown = _shutdown
    logger.info(
        "rss ingest runner started poll_interval=%ds block_duration=%ds",
        POLL_INTERVAL,
        BLOCK_DURATION,
    )
    _install_signal_handlers(shutdown)
    listener_task = asyncio.create_task(_listen_for_new_sources())

    try:
        loop = asyncio.get_running_loop()
        while not shutdown.is_set():
            try:
                await _run_once()
            except Exception:
                logger.exception("unexpected error in ingest loop")

            deadline = loop.time() + POLL_INTERVAL
            while loop.time() < deadline and not shutdown.is_set():
                if _immediate:
                    source_id_str = _immediate.popleft()
                    try:
                        source_id = UUID(source_id_str)
                    except ValueError:
                        logger.warning("invalid UUID in notify payload: %s", source_id_str)
                        continue
                    asyncio.create_task(_fetch_one_source(source_id))
                    continue
                remaining = deadline - loop.time()
                try:
                    await asyncio.wait_for(
                        shutdown.wait(), timeout=min(1.0, remaining)
                    )
                except asyncio.TimeoutError:
                    pass
    finally:
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener_task
        logger.info("rss ingest runner stopped")
