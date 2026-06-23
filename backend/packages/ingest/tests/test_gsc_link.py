"""Tests for ingest.gsc.link_articles — GSC page → article_gsc_metric mapping."""

import uuid
from datetime import date, datetime, timezone

import pytest
from core.db import get_session
from core.models import Article, ArticleGscMetric, ContentSource, GscPage, SourceType
from ingest.gsc import _extract_id_suffix, _normalize_url, link_articles
from sqlalchemy import select

pytestmark = pytest.mark.usefixtures("null_pool_db")


# ---------------------------------------------------------------------------
# Unit tests: URL helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        # scheme stripping
        ("https://www.tempo.co/bisnis/artikel-satu", "tempo.co/bisnis/artikel-satu"),
        ("http://www.tempo.co/bisnis/artikel-satu", "tempo.co/bisnis/artikel-satu"),
        # www/en/m prefix stripping
        ("https://en.tempo.co/read/2105904/slug", "tempo.co/read/2105904/slug"),
        ("https://m.tempo.co/read/2105904/slug", "tempo.co/read/2105904/slug"),
        # no prefix
        ("https://tempo.co/bisnis/artikel", "tempo.co/bisnis/artikel"),
        # query + fragment stripping
        ("https://www.tempo.co/page?utm=1#section", "tempo.co/page"),
        ("https://www.tempo.co/page#section", "tempo.co/page"),
        # trailing slash
        ("https://www.tempo.co/bisnis/artikel/", "tempo.co/bisnis/artikel"),
        # lowercase
        ("https://WWW.TEMPO.CO/Bisnis/Artikel", "tempo.co/bisnis/artikel"),
    ],
)
def test_normalize_url(url: str, expected: str) -> None:
    assert _normalize_url(url) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        # standard Tempo slug — trailing dash+digits
        ("https://www.tempo.co/bisnis/judul-artikel-2133891", "2133891"),
        # double dash
        ("https://www.tempo.co/bisnis/judul--2066109", "2066109"),
        # trailing slash after ID
        ("https://www.tempo.co/bisnis/judul-2133891/", "2133891"),
        # en.tempo.co /read/<id>/ format
        ("https://en.tempo.co/read/2105904/this-weekends-moon", "2105904"),
        # fewer than 6 trailing digits — does not match _TEMPO_ID_TRAIL
        ("https://www.tempo.co/bisnis/judul-12345", None),
        # no ID
        ("https://www.tempo.co/bisnis/artikel-tanpa-nomor", None),
        # short number not at end shouldn't trigger
        ("https://www.tempo.co/2026/05/artikel", None),
    ],
)
def test_extract_id_suffix(url: str, expected: str | None) -> None:
    assert _extract_id_suffix(url) == expected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_internal_article(session, url: str) -> uuid.UUID:
    src = ContentSource(
        id=uuid.uuid4(),
        name="Tempo",
        url=f"https://rss.tempo.co/{uuid.uuid4()}",
        source_type=SourceType.internal,
    )
    art = Article(
        id=uuid.uuid4(),
        source_id=src.id,
        title="T",
        url=url,
        published_at=datetime(2026, 5, 28, 10, 0),
    )
    session.add_all([src, art])
    await session.flush()
    return art.id


async def _make_gsc_page(
    session,
    page_url: str,
    *,
    clicks: int = 10,
    impressions: int = 200,
    avg_position: float = 8.5,
    period_start: date = date(2026, 5, 26),
    period_end: date = date(2026, 6, 1),
) -> None:
    session.add(
        GscPage(
            id=uuid.uuid4(),
            page_url=page_url,
            clicks=clicks,
            impressions=impressions,
            ctr=clicks / impressions,
            avg_position=avg_position,
            period_start=period_start,
            period_end=period_end,
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    await session.flush()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


async def test_exact_match_populates_metric() -> None:
    url = "https://www.tempo.co/bisnis/kenaikan-harga-beras-2133891"
    async with get_session() as session:
        art_id = await _make_internal_article(session, url)
        await _make_gsc_page(session, url, clicks=15, impressions=300, avg_position=7.0)
        await session.commit()

    async with get_session() as session:
        count = await link_articles(session, gsc_fetch_days=30)

    assert count == 1
    async with get_session() as session:
        metric = (
            await session.execute(
                select(ArticleGscMetric).where(ArticleGscMetric.article_id == art_id)
            )
        ).scalar_one()
    assert metric.impressions == 300
    assert metric.clicks == 15
    assert metric.avg_position == pytest.approx(7.0)
    assert metric.ctr == pytest.approx(15 / 300)


async def test_trailing_id_fallback_when_path_differs() -> None:
    """Article URL has a double-dash slug; GSC page URL has single dash — exact
    normalized match fails but trailing-ID fallback still links them."""
    art_url = "https://www.tempo.co/bisnis/harga-bahan-bakar--2066109"
    gsc_url = "https://www.tempo.co/bisnis/harga-bahan-bakar-2066109"
    async with get_session() as session:
        art_id = await _make_internal_article(session, art_url)
        await _make_gsc_page(session, gsc_url, impressions=100, clicks=5, avg_position=12.0)
        await session.commit()

    async with get_session() as session:
        count = await link_articles(session, gsc_fetch_days=30)

    assert count == 1
    async with get_session() as session:
        metric = (
            await session.execute(
                select(ArticleGscMetric).where(ArticleGscMetric.article_id == art_id)
            )
        ).scalar_one()
    assert metric.impressions == 100


async def test_non_internal_articles_not_linked() -> None:
    async with get_session() as session:
        src = ContentSource(
            id=uuid.uuid4(),
            name="Detik",
            url="https://detik.com/feed",
            source_type=SourceType.rss,
        )
        art = Article(
            id=uuid.uuid4(),
            source_id=src.id,
            title="T",
            url="https://www.detik.com/berita/artikel-1234567",
            published_at=datetime(2026, 5, 28, 10, 0),
        )
        session.add_all([src, art])
        await _make_gsc_page(session, "https://www.detik.com/berita/artikel-1234567")
        await session.commit()

    async with get_session() as session:
        count = await link_articles(session, gsc_fetch_days=30)

    assert count == 0


async def test_multi_period_creates_separate_rows() -> None:
    url = "https://www.tempo.co/nasional/artikel-penting-2200001"
    async with get_session() as session:
        art_id = await _make_internal_article(session, url)
        await _make_gsc_page(
            session, url, impressions=100, clicks=5,
            period_start=date(2026, 5, 19), period_end=date(2026, 5, 25),
        )
        await _make_gsc_page(
            session, url, impressions=150, clicks=8,
            period_start=date(2026, 5, 26), period_end=date(2026, 6, 1),
        )
        await session.commit()

    async with get_session() as session:
        count = await link_articles(session, gsc_fetch_days=30)

    assert count == 2
    async with get_session() as session:
        metrics = (
            await session.execute(
                select(ArticleGscMetric)
                .where(ArticleGscMetric.article_id == art_id)
                .order_by(ArticleGscMetric.period_start)
            )
        ).scalars().all()
    assert len(metrics) == 2
    assert metrics[0].impressions == 100
    assert metrics[1].impressions == 150


async def test_impression_weighted_avg_position() -> None:
    """When multiple gsc_page rows map to same article+period, avg_position is
    impression-weighted rather than a simple average."""
    url = "https://www.tempo.co/bisnis/artikel-dua-url-2300001"
    alt_url = "https://www.tempo.co/bisnis/artikel-dua-url-2300001/"  # trailing slash variant
    async with get_session() as session:
        art_id = await _make_internal_article(session, url)
        # Two slightly different URLs (trailing slash) → map to same article via norm
        # Use same period so they aggregate
        await _make_gsc_page(session, url, impressions=100, clicks=4, avg_position=5.0,
                              period_start=date(2026, 5, 26), period_end=date(2026, 6, 1))
        await _make_gsc_page(session, alt_url, impressions=300, clicks=9, avg_position=9.0,
                              period_start=date(2026, 5, 26), period_end=date(2026, 6, 1))
        await session.commit()

    async with get_session() as session:
        count = await link_articles(session, gsc_fetch_days=30)

    # Both URLs normalize to same → 1 aggregated row
    assert count == 1
    async with get_session() as session:
        metric = (
            await session.execute(
                select(ArticleGscMetric).where(ArticleGscMetric.article_id == art_id)
            )
        ).scalar_one()
    assert metric.impressions == 400
    assert metric.clicks == 13
    # Weighted avg_position = (5.0*100 + 9.0*300) / 400 = 3200/400 = 8.0
    assert metric.avg_position == pytest.approx(8.0)


async def test_gsc_outside_window_not_linked() -> None:
    """Rows whose period_end is older than gsc_fetch_days are excluded."""
    url = "https://www.tempo.co/bisnis/artikel-lama-2400001"
    async with get_session() as session:
        await _make_internal_article(session, url)
        # period_end is 60 days ago — outside a 7-day window
        await _make_gsc_page(
            session, url, impressions=100,
            period_start=date(2026, 4, 1), period_end=date(2026, 4, 7),
        )
        await session.commit()

    async with get_session() as session:
        # gsc_fetch_days=7: cutoff = today - 7d; period_end=2026-04-07 is well before that
        count = await link_articles(session, gsc_fetch_days=7)

    assert count == 0


async def test_upsert_updates_existing_row() -> None:
    url = "https://www.tempo.co/bisnis/artikel-update-2500001"
    async with get_session() as session:
        art_id = await _make_internal_article(session, url)
        await _make_gsc_page(session, url, impressions=100, clicks=5, avg_position=8.0)
        await session.commit()

    async with get_session() as session:
        await link_articles(session, gsc_fetch_days=30)

    # Update gsc_page with fresher numbers for same period
    async with get_session() as session:
        page = (
            await session.execute(select(GscPage).where(GscPage.page_url == url))
        ).scalar_one()
        page.impressions = 500
        page.clicks = 25
        await session.commit()

    async with get_session() as session:
        await link_articles(session, gsc_fetch_days=30)

    async with get_session() as session:
        metric = (
            await session.execute(
                select(ArticleGscMetric).where(ArticleGscMetric.article_id == art_id)
            )
        ).scalar_one()
    assert metric.impressions == 500
    assert metric.clicks == 25
