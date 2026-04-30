import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        await conn.begin()
        for table in (
            "cluster_insight",
            "article_cluster_member",
            "article_cluster",
            "cluster_run",
            "article_embedding",
            "article_gsc_metric",
            "trend_signal_article",
            "trend_signal",
            "article",
            "content_source",
        ):
            await conn.execute(text(f"DELETE FROM {table}"))
        session = AsyncSession(conn, expire_on_commit=False)
        await session.begin_nested()
        yield session
        await session.close()
        await conn.rollback()
    await engine.dispose()
