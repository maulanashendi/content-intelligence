import math
import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from core.db import get_session
from core.models import Article, ContentSource, ScrapeStatus, SourceStatus, SourceType
from ingest.trends import _extract_traffic_number, _parse_trends_feed, _resolve_source, ingest_trends
from sqlalchemy import select

NOW = datetime(2026, 5, 2, 6, 0, 0)

_SAMPLE_FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:ht="https://trends.google.com/trending/rss">
  <channel>
    <title>Google Trends - Indonesia</title>
    <item>
      <title>Prabowo</title>
      <ht:approx_traffic>500K+</ht:approx_traffic>
      <ht:news_item>
        <ht:news_item_title>Prabowo Bicara Ekonomi</ht:news_item_title>
        <ht:news_item_url>https://www.cnnindonesia.com/nasional/prabowo-bicara</ht:news_item_url>
      </ht:news_item>
      <ht:news_item>
        <ht:news_item_title>Prabowo Kunjungi Jepang</ht:news_item_title>
        <ht:news_item_url>https://www.detik.com/news/prabowo-jepang</ht:news_item_url>
      </ht:news_item>
    </item>
    <item>
      <title>IHSG</title>
      <ht:approx_traffic>100K+</ht:approx_traffic>
      <ht:news_item>
        <ht:news_item_title>IHSG Naik Tipis</ht:news_item_title>
        <ht:news_item_url>https://www.kontan.co.id/news/ihsg-naik</ht:news_item_url>
      </ht:news_item>
    </item>
    <item>
      <title>Kosong</title>
    </item>
  </channel>
</rss>"""


# ---------------------------------------------------------------------------
# _extract_traffic_number — normalization to 0-100
# ---------------------------------------------------------------------------


def test_extract_traffic_number_returns_none_for_empty() -> None:
    assert _extract_traffic_number(None) is None
    assert _extract_traffic_number("") is None


def test_extract_traffic_number_normalizes_thousands() -> None:
    score = _extract_traffic_number("5K+")
    assert score is not None
    assert 0.0 < score < 100.0


def test_extract_traffic_number_normalizes_millions() -> None:
    score = _extract_traffic_number("1M+")
    assert score is not None
    assert score == pytest.approx(100.0, abs=0.1)


def test_extract_traffic_number_higher_traffic_gives_higher_score() -> None:
    low = _extract_traffic_number("10K+")
    high = _extract_traffic_number("500K+")
    assert low is not None and high is not None
    assert high > low


def test_extract_traffic_number_500k_roughly_95() -> None:
    score = _extract_traffic_number("500K+")
    assert score is not None
    expected = math.log1p(500_000) / math.log1p(1_000_000) * 100
    assert score == pytest.approx(round(expected, 2), abs=0.01)


def test_extract_traffic_number_returns_none_for_non_numeric() -> None:
    assert _extract_traffic_number("N/A") is None


# ---------------------------------------------------------------------------
# _parse_trends_feed — raw XML parsing (xml.etree.ElementTree)
# ---------------------------------------------------------------------------


def test_parse_trends_feed_extracts_keywords() -> None:
    trends = _parse_trends_feed(_SAMPLE_FEED_XML, NOW)
    keywords = [t["keyword"] for t in trends]
    assert "Prabowo" in keywords
    assert "IHSG" in keywords


def test_parse_trends_feed_interest_score_is_not_none() -> None:
    trends = _parse_trends_feed(_SAMPLE_FEED_XML, NOW)
    prabowo = next(t for t in trends if t["keyword"] == "Prabowo")
    assert prabowo["interest_score"] is not None
    assert prabowo["interest_score"] > 0


def test_parse_trends_feed_extracts_article_url() -> None:
    trends = _parse_trends_feed(_SAMPLE_FEED_XML, NOW)
    prabowo = next(t for t in trends if t["keyword"] == "Prabowo")
    assert len(prabowo["articles"]) == 2
    assert prabowo["articles"][0]["url"] == "https://www.cnnindonesia.com/nasional/prabowo-bicara"
    assert prabowo["articles"][0]["title"] == "Prabowo Bicara Ekonomi"
    assert prabowo["articles"][1]["url"] == "https://www.detik.com/news/prabowo-jepang"
    assert prabowo["articles"][1]["title"] == "Prabowo Kunjungi Jepang"


def test_parse_trends_feed_captures_all_news_items() -> None:
    trends = _parse_trends_feed(_SAMPLE_FEED_XML, NOW)
    prabowo = next(t for t in trends if t["keyword"] == "Prabowo")
    assert len(prabowo["articles"]) == 2


def test_parse_trends_feed_entry_without_news_item_has_empty_articles() -> None:
    trends = _parse_trends_feed(_SAMPLE_FEED_XML, NOW)
    kosong = next((t for t in trends if t["keyword"] == "Kosong"), None)
    assert kosong is not None
    assert kosong["articles"] == []


def test_parse_trends_feed_skips_entries_without_title() -> None:
    xml = (
        '<?xml version="1.0"?>'
        '<rss version="2.0" xmlns:ht="https://trends.google.com/trending/rss">'
        "<channel><item><title>  </title></item></channel></rss>"
    )
    assert _parse_trends_feed(xml, NOW) == []


# ---------------------------------------------------------------------------
# _resolve_source — base-domain matching
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def detik_source(null_pool_db) -> ContentSource:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Detik Finance",
        url="https://rss.detik.com/index.php/finance",
        source_type=SourceType.rss,
        is_enabled=True,
        status=SourceStatus.active,
    )
    async with get_session() as session:
        session.add(source)
        await session.commit()
        await session.refresh(source)
    return source


@pytest_asyncio.fixture
async def kontan_source(null_pool_db) -> ContentSource:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Kontan Ekonomi",
        url="https://www.kontan.co.id/rss/ekonomi.xml",
        source_type=SourceType.rss,
        is_enabled=True,
        status=SourceStatus.active,
    )
    async with get_session() as session:
        session.add(source)
        await session.commit()
        await session.refresh(source)
    return source


@pytest.mark.asyncio
async def test_resolve_source_matches_article_subdomain_to_rss_source(
    detik_source: ContentSource,
) -> None:
    async with get_session() as session:
        result = await _resolve_source(session, "https://finance.detik.com/berita/harga-beras")
    assert result == detik_source.id


@pytest.mark.asyncio
async def test_resolve_source_matches_www_subdomain(
    detik_source: ContentSource,
) -> None:
    async with get_session() as session:
        result = await _resolve_source(session, "https://www.detik.com/finance/article")
    assert result == detik_source.id


@pytest.mark.asyncio
async def test_resolve_source_matches_cctld_domain(
    kontan_source: ContentSource,
) -> None:
    async with get_session() as session:
        result = await _resolve_source(session, "https://www.kontan.co.id/news/ihsg-naik")
    assert result == kontan_source.id


@pytest.mark.asyncio
async def test_resolve_source_returns_none_for_unknown_domain(
    detik_source: ContentSource,
) -> None:
    async with get_session() as session:
        result = await _resolve_source(session, "https://www.tribunnews.com/ekonomi/article")
    assert result is None


# ---------------------------------------------------------------------------
# ingest_trends — scrape_status regression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_trends_sets_scrape_status_pending(null_pool_db) -> None:
    async with get_session() as session:
        source = ContentSource(
            id=uuid.uuid4(),
            name="Detik",
            url="https://detik.com/rss",
            source_type=SourceType.rss,
            is_enabled=True,
            status=SourceStatus.active,
        )
        session.add(source)
        await session.commit()

    feed_xml = """\
<?xml version="1.0"?>
<rss version="2.0" xmlns:ht="https://trends.google.com/trending/rss">
  <channel>
    <item>
      <title>harga beras</title>
      <ht:approx_traffic>50K+</ht:approx_traffic>
      <ht:news_item>
        <ht:news_item_title>Harga beras naik</ht:news_item_title>
        <ht:news_item_url>https://detik.com/foo</ht:news_item_url>
      </ht:news_item>
    </item>
  </channel>
</rss>"""

    class FakeResp:
        text = feed_xml

        def raise_for_status(self) -> None: ...

    class FakeClient:
        async def get(self, url: str) -> FakeResp:
            return FakeResp()

    await ingest_trends(FakeClient())  # type: ignore[arg-type]

    async with get_session() as session:
        article = (
            await session.execute(select(Article).where(Article.url == "https://detik.com/foo"))
        ).scalar_one()
    assert article.scrape_status == ScrapeStatus.pending
