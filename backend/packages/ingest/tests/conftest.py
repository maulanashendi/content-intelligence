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

_INGEST_TABLES = ("trend_signal_article", "trend_signal", "article", "content_source")

# ---------------------------------------------------------------------------
# Feed XML fixtures — mirrors actual provider payloads used in regression tests
# ---------------------------------------------------------------------------


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


@pytest.fixture
def google_news_sitemap_xml() -> bytes:
    """Google News sitemap — mirrors Suara.com: CDATA-wrapped loc, +07:00 dates."""
    return b"""\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc><![CDATA[ https://www.suara.com/news/2026/05/29/150041/viral-pengantin-pria-pakai-selendang-bentuk-bunga ]]></loc>
    <news:news>
      <news:publication><news:name>Suara.com</news:name></news:publication>
      <news:publication_date>2026-05-29T15:00:41+07:00</news:publication_date>
      <news:title><![CDATA[Viral Pengantin Pria Pakai Selendang Bentuk Bunga Menjuntai]]></news:title>
    </news:news>
  </url>
  <url>
    <loc><![CDATA[ https://www.suara.com/news/2026/05/29/140000/artikel-kedua-berita-penting ]]></loc>
    <news:news>
      <news:publication_date>2026-05-29T14:00:00+07:00</news:publication_date>
      <news:title><![CDATA[Artikel Kedua Berita Penting]]></news:title>
    </news:news>
  </url>
</urlset>"""


@pytest.fixture
def standard_sitemap_xml() -> bytes:
    """Standard sitemap — <urlset><url><loc> + <lastmod>."""
    return b"""\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/berita/artikel-penting-satu</loc>
    <lastmod>2026-05-28T10:00:00</lastmod>
  </url>
  <url>
    <loc>https://example.com/berita/artikel-kedua-terbaru</loc>
    <lastmod>2026-05-29T08:30:00Z</lastmod>
  </url>
</urlset>"""


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


@pytest_asyncio.fixture
async def internal_source() -> ContentSource:
    """source_type=internal — represents Tempo's own RSS feeds (rss.tempo.co)."""
    source = ContentSource(
        id=uuid.uuid4(),
        name="Tempo – Bisnis",
        url="https://rss.tempo.co/bisnis",
        source_type=SourceType.internal,
        is_enabled=True,
    )
    async with get_session() as session:
        session.add(source)
        await session.commit()
        await session.refresh(source)
    return source
