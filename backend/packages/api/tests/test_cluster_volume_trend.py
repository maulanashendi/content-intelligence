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


def _article(source_id: uuid.UUID, published_at: datetime) -> Article:
    return Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title="A",
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
