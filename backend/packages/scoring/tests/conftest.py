from collections.abc import AsyncIterator

import pytest
from core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(conn, expire_on_commit=False) as sess:
            yield sess
        await conn.rollback()
    await engine.dispose()
