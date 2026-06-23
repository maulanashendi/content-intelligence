import uuid
from datetime import UTC, datetime, timedelta, timezone

from core.models import Article, ContentSource, SourceType
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_WIB = timezone(timedelta(hours=7))
_NOW = datetime.now(UTC).replace(tzinfo=None)


def _source(source_type: SourceType = SourceType.rss, *, name: str = "Vol Source") -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        name=name,
        url=f"https://test-{uuid.uuid4()}.com/rss",
        source_type=source_type,
    )


def _article(
    source_id: uuid.UUID,
    *,
    published_at: datetime | None = None,
    created_at: datetime | None = None,
    title: str = "Vol Article",
) -> Article:
    a = Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title=title,
        url=f"https://test-{uuid.uuid4()}.com/a",
        published_at=published_at,
    )
    if created_at is not None:
        a.created_at = created_at
    return a


def _wib_day_bucket_utc_iso(ts_naive_utc: datetime) -> str:
    """UTC instant (Z-suffixed) of the WIB-day bucket that contains ts."""
    wib = ts_naive_utc.replace(tzinfo=UTC).astimezone(_WIB)
    wib_mid = wib.replace(hour=0, minute=0, second=0, microsecond=0)
    return wib_mid.astimezone(UTC).isoformat().replace("+00:00", "Z")


async def test_volume_trend_response_shape(client: AsyncClient) -> None:
    r = await client.get("/api/v1/articles/volume-trend")
    assert r.status_code == 200
    d = r.json()
    assert d["bucket"] == "day"
    assert isinstance(d["buckets"], list)
    assert "generated_at" in d
    b = d["buckets"][0]
    assert set(b.keys()) == {"bucket_start", "competitor_count", "internal_count"}


async def test_volume_trend_day_has_30_dense_buckets(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    assert len(d["buckets"]) == 30


async def test_volume_trend_hour_has_48_dense_buckets(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/articles/volume-trend?bucket=hour")).json()
    assert d["bucket"] == "hour"
    assert len(d["buckets"]) == 48


async def test_volume_trend_invalid_bucket_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/articles/volume-trend?bucket=week")
    assert r.status_code == 422


async def test_volume_trend_empty_db_all_zero(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    assert len(d["buckets"]) == 30
    assert all(b["competitor_count"] == 0 and b["internal_count"] == 0 for b in d["buckets"])


async def test_volume_trend_splits_competitor_and_internal(
    session: AsyncSession, client: AsyncClient
) -> None:
    rss = _source(SourceType.rss, name="Kompas")
    internal = _source(SourceType.internal, name="Tempo")
    ts = _NOW - timedelta(hours=3)
    session.add_all(
        [rss, internal, _article(rss.id, published_at=ts), _article(internal.id, published_at=ts)]
    )
    await session.flush()

    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    by_start = {b["bucket_start"]: b for b in d["buckets"]}
    target = _wib_day_bucket_utc_iso(ts)
    assert by_start[target]["competitor_count"] == 1
    assert by_start[target]["internal_count"] == 1


async def test_volume_trend_buckets_by_wib_day_not_utc(
    session: AsyncSession, client: AsyncClient
) -> None:
    rss = _source(SourceType.rss)
    # 18:00 UTC → 01:00 WIB next day → belongs to the *next* WIB day's bucket.
    ts = (_NOW - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    session.add_all([rss, _article(rss.id, published_at=ts)])
    await session.flush()

    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    by_start = {b["bucket_start"]: b for b in d["buckets"]}
    target = _wib_day_bucket_utc_iso(ts)
    # Counted exactly once, in the WIB-day bucket.
    assert sum(b["competitor_count"] for b in d["buckets"]) == 1
    assert by_start[target]["competitor_count"] == 1


async def test_volume_trend_uses_created_at_when_published_null(
    session: AsyncSession, client: AsyncClient
) -> None:
    rss = _source(SourceType.rss)
    ts = _NOW - timedelta(hours=5)
    session.add_all([rss, _article(rss.id, published_at=None, created_at=ts)])
    await session.flush()

    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    by_start = {b["bucket_start"]: b for b in d["buckets"]}
    target = _wib_day_bucket_utc_iso(ts)
    assert by_start[target]["competitor_count"] == 1


async def test_volume_trend_excludes_articles_older_than_window(
    session: AsyncSession, client: AsyncClient
) -> None:
    rss = _source(SourceType.rss)
    session.add_all([rss, _article(rss.id, published_at=_NOW - timedelta(days=40))])
    await session.flush()

    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    assert sum(b["competitor_count"] for b in d["buckets"]) == 0


async def test_volume_trend_bucket_starts_sorted_unique_utc(client: AsyncClient) -> None:
    d = (await client.get("/api/v1/articles/volume-trend?bucket=day")).json()
    starts = [b["bucket_start"] for b in d["buckets"]]
    assert all(s.endswith("Z") for s in starts)
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)
