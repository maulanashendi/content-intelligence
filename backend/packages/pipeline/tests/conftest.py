import uuid

import pytest_asyncio
from core.config import settings
from core.db import get_session
from core.models import ContentSource, SourceType
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

E2E_TABLES = (
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
)


@pytest_asyncio.fixture
async def clean_db():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            for table in E2E_TABLES:
                await conn.execute(text(f"DELETE FROM {table}"))
        yield
    finally:
        async with engine.begin() as conn:
            for table in E2E_TABLES:
                await conn.execute(text(f"DELETE FROM {table}"))
        await engine.dispose()


@pytest_asyncio.fixture
async def rss_source(clean_db) -> ContentSource:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Fake RSS",
        url="https://fake.example.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
    )
    async with get_session() as session:
        session.add(source)
        await session.commit()
        await session.refresh(source)
    return source
