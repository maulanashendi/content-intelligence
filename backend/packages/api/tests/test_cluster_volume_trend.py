import uuid
from datetime import UTC, datetime, timedelta

from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterRun,
    ContentSource,
    SourceType,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _source(source_type: SourceType, name: str) -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        name=name,
        url=f"https://test-{uuid.uuid4()}.com",
        source_type=source_type,
    )


def _article(source_id: uuid.UUID, published_at: datetime, title: str = "A") -> Article:
    return Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title=title,
        url=f"https://test-{uuid.uuid4()}.com/a",
        published_at=published_at,
    )


async def test_cluster_volume_trend_404_for_unknown_id(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/clusters/{uuid.uuid4()}/volume-trend?bucket=hour")
    assert r.status_code == 404


async def test_cluster_volume_trend_hour_has_48_buckets(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="C", is_current=True)
    session.add_all([run, cluster])
    await session.flush()

    d = (await client.get(f"/api/v1/clusters/{cluster.id}/volume-trend?bucket=hour")).json()
    assert d["bucket"] == "hour"
    assert len(d["buckets"]) == 48
    assert all(b["competitor_count"] == 0 and b["internal_count"] == 0 for b in d["buckets"])


async def test_cluster_volume_trend_day_has_30_buckets(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="D", is_current=True)
    session.add_all([run, cluster])
    await session.flush()

    d = (await client.get(f"/api/v1/clusters/{cluster.id}/volume-trend?bucket=day")).json()
    assert d["bucket"] == "day"
    assert len(d["buckets"]) == 30
    assert all(b["competitor_count"] == 0 and b["internal_count"] == 0 for b in d["buckets"])


async def test_cluster_volume_trend_counts_only_this_clusters_members(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="C", is_current=True)
    other = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="Other", is_current=True)
    rss = _source(SourceType.rss, "Kompas")
    internal = _source(SourceType.internal, "Tempo")
    ts = _NOW - timedelta(hours=2)
    a_comp = _article(rss.id, ts)
    a_int = _article(internal.id, ts)
    a_other = _article(rss.id, ts)
    session.add_all([run, cluster, other, rss, internal, a_comp, a_int, a_other])
    await session.flush()
    session.add_all([
        ArticleClusterMember(cluster_id=cluster.id, article_id=a_comp.id),
        ArticleClusterMember(cluster_id=cluster.id, article_id=a_int.id),
        ArticleClusterMember(cluster_id=other.id, article_id=a_other.id),
    ])
    await session.flush()

    d = (await client.get(f"/api/v1/clusters/{cluster.id}/volume-trend?bucket=hour")).json()
    assert sum(b["competitor_count"] for b in d["buckets"]) == 1
    assert sum(b["internal_count"] for b in d["buckets"]) == 1


async def test_cluster_volume_trend_response_shape_includes_competitor_avg(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="C", is_current=True)
    session.add_all([run, cluster])
    await session.flush()

    d = (await client.get(f"/api/v1/clusters/{cluster.id}/volume-trend?bucket=hour")).json()
    b = d["buckets"][0]
    assert set(b.keys()) == {
        "bucket_start",
        "competitor_count",
        "internal_count",
        "competitor_avg_per_source",
    }
    assert b["competitor_avg_per_source"] == 0.0


async def test_cluster_volume_trend_competitor_avg_per_source(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="C", is_current=True)
    source_a = _source(SourceType.rss, "Kompas")
    source_b = _source(SourceType.rss, "Detik")
    ts = _NOW - timedelta(hours=2)
    a1 = _article(source_a.id, ts, title="A1")
    a2 = _article(source_a.id, ts, title="A2")
    a3 = _article(source_a.id, ts, title="A3")
    b1 = _article(source_b.id, ts, title="B1")
    session.add_all([run, cluster, source_a, source_b, a1, a2, a3, b1])
    await session.flush()
    session.add_all(
        [
            ArticleClusterMember(cluster_id=cluster.id, article_id=a1.id),
            ArticleClusterMember(cluster_id=cluster.id, article_id=a2.id),
            ArticleClusterMember(cluster_id=cluster.id, article_id=a3.id),
            ArticleClusterMember(cluster_id=cluster.id, article_id=b1.id),
        ]
    )
    await session.flush()

    d = (await client.get(f"/api/v1/clusters/{cluster.id}/volume-trend?bucket=hour")).json()
    total_competitor = sum(bkt["competitor_count"] for bkt in d["buckets"])
    assert total_competitor == 4
    matching = [bkt for bkt in d["buckets"] if bkt["competitor_count"] == 4]
    assert len(matching) == 1
    assert matching[0]["competitor_avg_per_source"] == 2.0


async def test_cluster_volume_trend_competitor_avg_per_source_zero_when_no_competitor(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="C", is_current=True)
    internal = _source(SourceType.internal, "Tempo")
    ts = _NOW - timedelta(hours=2)
    a_int = _article(internal.id, ts, title="Internal1")
    session.add_all([run, cluster, internal, a_int])
    await session.flush()
    session.add_all([ArticleClusterMember(cluster_id=cluster.id, article_id=a_int.id)])
    await session.flush()

    d = (await client.get(f"/api/v1/clusters/{cluster.id}/volume-trend?bucket=hour")).json()
    assert all(bkt["competitor_avg_per_source"] == 0.0 for bkt in d["buckets"])
