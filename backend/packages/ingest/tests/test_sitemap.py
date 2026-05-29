"""
Integration tests for ingest.sitemap — ingest_sitemap() function.

Focus: semantic regressions found during incident investigation.

Tempo regression (2026-05-29)
------------------------------
Sources with source_type=internal were routed to ingest_sitemap(). Their URLs
(rss.tempo.co/*) serve RSS 2.0 XML, not sitemap XML. The old sitemap parser
looked for <url><loc> elements in the sitemap namespace and found none, so
every cycle logged "entries=0" and inserted nothing.

Fix: parse_feed() now detects the format from the response bytes and routes to
the correct parser, with fallback through all three parsers if the primary
returns 0 entries.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from core.db import get_session
from core.models import Article, ContentSource, SourceStatus
from ingest.sitemap import ingest_sitemap
from sqlalchemy import select


def _mock_client_for_internal(
    source: ContentSource,
    body: bytes,
    status: int = 200,
) -> AsyncMock:
    """Mock client that returns `body` for the given source URL."""
    resp = MagicMock()
    resp.status_code = status
    resp.content = body
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status}", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status = MagicMock()

    async def _get(url: str, **_):
        return resp

    mock = AsyncMock()
    mock.get = AsyncMock(side_effect=_get)
    return mock


# ---------------------------------------------------------------------------
# Tempo regression — source_type=internal serving RSS 2.0 XML
#
# Previously: sitemap.py called _parse_sitemap() which expected <urlset><loc>
# and returned 0 entries for any RSS/Atom document.
# After fix: parse_feed() detects <rss> root and routes to _parse_rss().
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_sitemap_rss_feed_inserts_articles(
    internal_source: ContentSource,
    rss_feed_xml: str,
) -> None:
    """Tempo regression: ingest_sitemap() must insert articles when the
    internal source serves RSS XML, not return 0 silently."""
    client = _mock_client_for_internal(internal_source, rss_feed_xml.encode())
    total = await ingest_sitemap(client)

    assert total == 2, (
        "ingest_sitemap() returned 0 for an RSS-format internal source. "
        "This is the Tempo regression: sitemap parser was ignoring RSS feeds."
    )


@pytest.mark.asyncio
async def test_ingest_sitemap_rss_feed_articles_have_real_titles_and_dates(
    internal_source: ContentSource,
    rss_feed_xml: str,
) -> None:
    """Articles ingested from an RSS feed (internal source) must carry the
    full editorial title from <title> and a parsed published_at, not URL-derived
    slugs with null dates."""
    client = _mock_client_for_internal(internal_source, rss_feed_xml.encode())
    await ingest_sitemap(client)

    async with get_session() as session:
        rows = (
            (await session.execute(select(Article).where(Article.source_id == internal_source.id)))
            .scalars()
            .all()
        )

    assert {a.url for a in rows} == {
        "https://example.com/article-one",
        "https://example.com/article-two",
    }
    titles = {a.title for a in rows}
    assert "Article One" in titles
    assert "Article Two" in titles

    dated = [a for a in rows if a.published_at is not None]
    assert len(dated) == 2
    for article in dated:
        assert article.published_at.tzinfo is None


@pytest.mark.asyncio
async def test_ingest_sitemap_rss_feed_sets_source_active(
    internal_source: ContentSource,
    rss_feed_xml: str,
) -> None:
    client = _mock_client_for_internal(internal_source, rss_feed_xml.encode())
    await ingest_sitemap(client)

    async with get_session() as session:
        source = await session.get(ContentSource, internal_source.id)

    assert source.status == SourceStatus.active
    assert source.last_fetched_at is not None


@pytest.mark.asyncio
async def test_ingest_sitemap_rss_feed_is_idempotent(
    internal_source: ContentSource,
    rss_feed_xml: str,
) -> None:
    client = _mock_client_for_internal(internal_source, rss_feed_xml.encode())
    first = await ingest_sitemap(client)
    second = await ingest_sitemap(client)

    assert first == 2
    assert second == 0

    async with get_session() as session:
        rows = (
            (await session.execute(select(Article).where(Article.source_id == internal_source.id)))
            .scalars()
            .all()
        )
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Google News Sitemap — source_type=internal (e.g. future Tempo sitemap)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_sitemap_google_news_sitemap_inserts_articles(
    internal_source: ContentSource,
    google_news_sitemap_xml: bytes,
) -> None:
    client = _mock_client_for_internal(internal_source, google_news_sitemap_xml)
    total = await ingest_sitemap(client)
    assert total == 2


@pytest.mark.asyncio
async def test_ingest_sitemap_google_news_sitemap_title_from_news_element(
    internal_source: ContentSource,
    google_news_sitemap_xml: bytes,
) -> None:
    """Title must come from <news:title>, not URL slug."""
    client = _mock_client_for_internal(internal_source, google_news_sitemap_xml)
    await ingest_sitemap(client)

    async with get_session() as session:
        rows = (
            (await session.execute(select(Article).where(Article.source_id == internal_source.id)))
            .scalars()
            .all()
        )
    titles = {a.title for a in rows}
    assert "Viral Pengantin Pria Pakai Selendang Bentuk Bunga Menjuntai" in titles


@pytest.mark.asyncio
async def test_ingest_sitemap_google_news_sitemap_naive_utc_dates(
    internal_source: ContentSource,
    google_news_sitemap_xml: bytes,
) -> None:
    """Timezone-aware dates (+07:00) must be converted to naive UTC before
    INSERT, otherwise asyncpg raises DataError."""
    client = _mock_client_for_internal(internal_source, google_news_sitemap_xml)
    await ingest_sitemap(client)

    async with get_session() as session:
        rows = (
            (await session.execute(select(Article).where(Article.source_id == internal_source.id)))
            .scalars()
            .all()
        )
    for article in rows:
        if article.published_at is not None:
            assert article.published_at.tzinfo is None
            assert article.published_at == datetime(2026, 5, 29, 8, 0, 41)
            return
    pytest.fail("No article with published_at found")


# ---------------------------------------------------------------------------
# Standard sitemap — source_type=internal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_sitemap_standard_sitemap_inserts_articles(
    internal_source: ContentSource,
    standard_sitemap_xml: bytes,
) -> None:
    client = _mock_client_for_internal(internal_source, standard_sitemap_xml)
    total = await ingest_sitemap(client)
    assert total == 2


@pytest.mark.asyncio
async def test_ingest_sitemap_standard_sitemap_url_is_loc_element(
    internal_source: ContentSource,
    standard_sitemap_xml: bytes,
) -> None:
    client = _mock_client_for_internal(internal_source, standard_sitemap_xml)
    await ingest_sitemap(client)

    async with get_session() as session:
        rows = (
            (await session.execute(select(Article).where(Article.source_id == internal_source.id)))
            .scalars()
            .all()
        )
    urls = {a.url for a in rows}
    assert "https://example.com/berita/artikel-penting-satu" in urls
    assert "https://example.com/berita/artikel-kedua-terbaru" in urls


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_sitemap_http_error_marks_source_error(
    internal_source: ContentSource,
) -> None:
    client = _mock_client_for_internal(internal_source, b"", status=500)
    total = await ingest_sitemap(client)

    assert total == 0

    async with get_session() as session:
        source = await session.get(ContentSource, internal_source.id)
    assert source.status == SourceStatus.error


@pytest.mark.asyncio
async def test_ingest_sitemap_network_error_marks_source_error(
    internal_source: ContentSource,
) -> None:
    mock = AsyncMock()
    mock.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    total = await ingest_sitemap(mock)

    assert total == 0

    async with get_session() as session:
        source = await session.get(ContentSource, internal_source.id)
    assert source.status == SourceStatus.error


@pytest.mark.asyncio
async def test_ingest_sitemap_garbage_body_inserts_zero_does_not_crash(
    internal_source: ContentSource,
) -> None:
    client = _mock_client_for_internal(internal_source, b"<<garbage not xml>>")
    total = await ingest_sitemap(client)
    assert total == 0
    # Source should still be marked active (fetch succeeded, parse returned nothing)
    async with get_session() as session:
        source = await session.get(ContentSource, internal_source.id)
    assert source.status == SourceStatus.active


# ---------------------------------------------------------------------------
# No enabled sources — must not crash and return 0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_sitemap_no_enabled_sources_returns_zero() -> None:
    mock = AsyncMock()
    total = await ingest_sitemap(mock)
    assert total == 0
    mock.get.assert_not_called()
