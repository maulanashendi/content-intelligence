"""
Integration tests — require a live PostgreSQL instance.

Covers:
- pg_notify / LISTEN round-trip: notification arrives on the correct channel
"""

import asyncio
import uuid

import asyncpg
import pytest
from core.config import settings
from core.db import get_session
from sqlalchemy import text


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
