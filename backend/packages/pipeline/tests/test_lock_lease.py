"""Tests for the self-healing lock lease (D30).

pipeline_group_lock is NOT in clean_db's E2E_TABLES, so each test cleans the
table itself in a setup/teardown fixture.
"""

from datetime import UTC, datetime, timedelta

import core.db as _core_db
import pytest
import pytest_asyncio
from core.config import settings
from core.db import get_session
from core.models import PipelineGroupLock
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from pipeline.runner import _acquire_lock, _release_lock

_GROUP = "test_lease_group"


@pytest_asyncio.fixture
async def lock_db():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    _core_db._engine = engine
    _core_db._session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM pipeline_group_lock WHERE group_name = :g"),
                {"g": _GROUP},
            )
        yield
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM pipeline_group_lock WHERE group_name = :g"),
                {"g": _GROUP},
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_acquire_lock_reaps_expired_lease(lock_db, monkeypatch):
    monkeypatch.setattr(settings, "pipeline_lock_lease_ttl_seconds", 300)

    expired_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)
    async with get_session() as session:
        session.add(PipelineGroupLock(group_name=_GROUP))
        await session.commit()
        await session.execute(
            text(
                "UPDATE pipeline_group_lock SET locked_at = :ts WHERE group_name = :g"
            ),
            {"ts": expired_at, "g": _GROUP},
        )
        await session.commit()

    acquired = await _acquire_lock(_GROUP)
    assert acquired is True, "expired lease must be reaped and new lock acquired"

    async with get_session() as session:
        rows = (
            await session.execute(
                select(PipelineGroupLock).where(PipelineGroupLock.group_name == _GROUP)
            )
        ).scalars().all()
    assert len(rows) == 1, "exactly one fresh lock row must remain"
    assert rows[0].locked_at > expired_at, "new locked_at must be more recent than the expired row"

    await _release_lock(_GROUP)


@pytest.mark.asyncio
async def test_acquire_lock_rejects_fresh_lease(lock_db, monkeypatch):
    monkeypatch.setattr(settings, "pipeline_lock_lease_ttl_seconds", 300)

    async with get_session() as session:
        session.add(PipelineGroupLock(group_name=_GROUP))
        await session.commit()

    acquired = await _acquire_lock(_GROUP)
    assert acquired is False, "fresh lease must not be reaped — lock must be refused"

    await _release_lock(_GROUP)
