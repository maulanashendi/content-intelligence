"""
Ingest test configuration.

The core problem: core.db creates a module-level engine with connection pooling.
pytest-asyncio (asyncio_mode=auto) gives each test its own event loop, so pool
connections from test N are bound to loop N. Test N+1 runs on a fresh loop and
gets "Future attached to a different loop" when it touches the shared pool.

Fix: the autouse `null_pool_db` fixture replaces core.db's session factory with
a NullPool version for each test. Each get_session() call creates a fresh
connection on the current test's loop. monkeypatch restores the originals after
each test. No other test packages are affected.
"""

import uuid

import pytest
import pytest_asyncio
from core.config import settings
from core.db import get_session
from core.models import ContentSource, SourceType
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

_INGEST_TABLES = ("article", "content_source")


@pytest.fixture(autouse=True)
async def null_pool_db(monkeypatch):
    import core.db as _core_db

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(_core_db, "_engine", engine)
    monkeypatch.setattr(_core_db, "_session_factory", factory)

    async with engine.begin() as conn:
        for table in _INGEST_TABLES:
            await conn.execute(text(f"DELETE FROM {table}"))

    yield

    async with engine.begin() as conn:
        for table in _INGEST_TABLES:
            await conn.execute(text(f"DELETE FROM {table}"))

    await engine.dispose()


@pytest.fixture
def rss_feed_xml() -> str:
    return """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article One</title>
      <link>https://example.com/article-one</link>
      <pubDate>Thu, 01 May 2026 06:00:00 +0000</pubDate>
      <description>First article summary.</description>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/article-two</link>
      <pubDate>Thu, 01 May 2026 07:00:00 +0000</pubDate>
      <description>Second article summary.</description>
    </item>
  </channel>
</rss>"""


@pytest_asyncio.fixture
async def rss_source() -> ContentSource:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Test Feed",
        url="https://example.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
    )
    async with get_session() as session:
        session.add(source)
        await session.commit()
        await session.refresh(source)
    return source
