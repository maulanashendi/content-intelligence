import core.db as _core_db
import pytest_asyncio
from core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

_TABLES = (
    "article_cluster_member",
    "cluster_insight",
    "article_cluster",
    "cluster_run",
    "article",
    "content_source",
)


@pytest_asyncio.fixture
async def clean_db():
    # Use NullPool and rebind core.db so get_session() inside pipeline code
    # does not pull connections from a previous test's event loop.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    _core_db._engine = engine
    _core_db._session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            for table in _TABLES:
                await conn.execute(text(f"DELETE FROM {table}"))
        yield
    finally:
        async with engine.begin() as conn:
            for table in _TABLES:
                await conn.execute(text(f"DELETE FROM {table}"))
        await engine.dispose()
