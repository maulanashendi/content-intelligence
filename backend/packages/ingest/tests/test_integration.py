"""
Integration tests — require a live PostgreSQL instance.

Covers:
- _run_once end-to-end: real DB (NullPool via autouse fixture), mocked HTTP → articles persisted
- pg_notify / LISTEN round-trip: notification arrives on the correct channel
"""

import asyncio
import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from core.config import settings
from core.db import get_session
from core.models import Article
from ingest.runner import _run_once
from sqlalchemy import select, text


# ---------------------------------------------------------------------------
# _run_once — full cycle with real DB, mocked HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_once_inserts_articles_into_db(rss_source, rss_feed_xml: str) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = rss_feed_xml
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_resp)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("ingest.runner.make_http_client", return_value=mock_cm):
        await _run_once()

    async with get_session() as session:
        rows = (
            await session.execute(
                select(Article).where(Article.source_id == rss_source.id)
            )
        ).scalars().all()

    assert len(rows) == 2
    assert {a.url for a in rows} == {
        "https://example.com/article-one",
        "https://example.com/article-two",
    }


@pytest.mark.asyncio
async def test_run_once_skips_blocked_source_does_not_insert(
    rss_source, rss_feed_xml: str
) -> None:
    import ingest.runner as _runner
    from datetime import UTC, datetime, timedelta

    _runner._blocked_until[rss_source.id] = datetime.now(UTC) + timedelta(hours=1)

    mock_http = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("ingest.runner.make_http_client", return_value=mock_cm):
        await _run_once()

    mock_http.get.assert_not_called()

    async with get_session() as session:
        rows = (
            await session.execute(
                select(Article).where(Article.source_id == rss_source.id)
            )
        ).scalars().all()

    assert len(rows) == 0
    _runner._blocked_until.clear()


# ---------------------------------------------------------------------------
# PostgreSQL LISTEN / NOTIFY round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pg_notify_delivered_to_listener() -> None:
    received: list[str] = []

    def _on_notify(conn, pid, channel, payload):
        received.append(payload)

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    listener = await asyncpg.connect(dsn=dsn)
    await listener.add_listener("rss_source_created", _on_notify)

    test_id = str(uuid.uuid4())
    async with get_session() as session:
        await session.execute(
            text("SELECT pg_notify('rss_source_created', :id)"),
            {"id": test_id},
        )
        await session.commit()

    await asyncio.sleep(0.2)

    assert received == [test_id]
    await listener.close()


@pytest.mark.asyncio
async def test_pg_notify_payload_is_valid_uuid() -> None:
    received: list[str] = []

    def _on_notify(conn, pid, channel, payload):
        received.append(payload)

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    listener = await asyncpg.connect(dsn=dsn)
    await listener.add_listener("rss_source_created", _on_notify)

    source_id = uuid.uuid4()
    async with get_session() as session:
        await session.execute(
            text("SELECT pg_notify('rss_source_created', :id)"),
            {"id": str(source_id)},
        )
        await session.commit()

    await asyncio.sleep(0.2)

    assert len(received) == 1
    assert uuid.UUID(received[0]) == source_id
    await listener.close()


# ---------------------------------------------------------------------------
# Listener pipeline: pg_notify → runner._immediate queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listener_routes_notify_to_immediate_queue() -> None:
    import ingest.runner as _runner

    _runner._immediate.clear()
    _runner._shutdown = asyncio.Event()

    listener_task = asyncio.create_task(_runner._listen_for_new_sources())
    await asyncio.sleep(0.5)

    source_id = uuid.uuid4()
    async with get_session() as session:
        await session.execute(
            text("SELECT pg_notify('rss_source_created', :id)"),
            {"id": str(source_id)},
        )
        await session.commit()

    for _ in range(20):
        if _runner._immediate:
            break
        await asyncio.sleep(0.1)

    payload = _runner._immediate.popleft()
    assert uuid.UUID(payload) == source_id

    _runner._shutdown.set()
    listener_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await listener_task


@pytest.mark.asyncio
async def test_runner_invalid_uuid_payload_logs_and_continues(caplog) -> None:
    import logging

    import ingest.runner as _runner

    fetch_calls: list = []

    async def _capture_fetch(source_id):
        fetch_calls.append(source_id)

    async def _seed_run_once() -> None:
        _runner._immediate.append("garbage-not-a-uuid")

    async def _noop_listener() -> None:
        await _runner._shutdown.wait()

    with patch("ingest.runner._run_once", _seed_run_once), \
         patch("ingest.runner._listen_for_new_sources", _noop_listener), \
         patch("ingest.runner._install_signal_handlers", lambda _e: None), \
         patch("ingest.runner._fetch_one_source", _capture_fetch), \
         caplog.at_level(logging.WARNING, logger="ingest.runner"):
        async def _stop_soon():
            await asyncio.sleep(0.2)
            _runner._shutdown.set()

        await asyncio.gather(_runner.run_loop(), _stop_soon())

    assert "invalid UUID" in caplog.text
    assert fetch_calls == []
