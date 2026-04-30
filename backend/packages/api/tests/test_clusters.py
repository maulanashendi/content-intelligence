import uuid
from datetime import UTC, datetime, timedelta

from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterInsight,
    ClusterRun,
    ContentSource,
    InsightRecommendation,
    SourceType,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _source(source_type: SourceType) -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        name="Test Source",
        url=f"https://test-{uuid.uuid4()}.com",
        source_type=source_type,
    )


def _article(source_id: uuid.UUID, published_at: datetime) -> Article:
    return Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title="Test Article",
        url=f"https://test-{uuid.uuid4()}.com/a",
        published_at=published_at,
    )


def _cluster_with_insight(
    run_id: uuid.UUID,
) -> tuple[ArticleCluster, ClusterInsight]:
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_id, label="Test", is_current=True)
    insight = ClusterInsight(
        id=uuid.uuid4(),
        cluster_id=cluster.id,
        recommendation=InsightRecommendation.trending,
        trend_velocity=0.9,
    )
    return cluster, insight


async def test_morning_excludes_cluster_with_recent_internal_article(
    session: AsyncSession, client: AsyncClient
) -> None:
    source = _source(SourceType.internal)
    article = _article(source.id, _NOW - timedelta(days=1))
    run = ClusterRun(id=uuid.uuid4())
    cluster, insight = _cluster_with_insight(run.id)
    member = ArticleClusterMember(cluster_id=cluster.id, article_id=article.id)

    session.add_all([source, article, run, cluster, member, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert str(cluster.id) not in ids


async def test_morning_includes_cluster_with_recent_external_article(
    session: AsyncSession, client: AsyncClient
) -> None:
    source = _source(SourceType.rss)
    article = _article(source.id, _NOW - timedelta(days=1))
    run = ClusterRun(id=uuid.uuid4())
    cluster, insight = _cluster_with_insight(run.id)
    member = ArticleClusterMember(cluster_id=cluster.id, article_id=article.id)

    session.add_all([source, article, run, cluster, member, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert str(cluster.id) in ids


async def test_cluster_detail_returns_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/clusters/{uuid.uuid4()}")
    assert response.status_code == 404
