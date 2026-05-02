from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        yield session
