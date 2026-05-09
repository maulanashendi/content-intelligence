import uuid
from datetime import UTC, datetime, timedelta

import pytest

from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterInsight,
    ClusterRun,
    ContentSource,
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
    *,
    tempo_covered: bool = False,
    trend_velocity: float = 0.5,
    competitor_count: int = 2,
    trend_match_count: int = 1,
    last_internal_days_ago: int | None = None,
    underperformed: bool = False,
) -> tuple[ArticleCluster, ClusterInsight]:
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_id, label="Test", is_current=True)
    insight = ClusterInsight(
        id=uuid.uuid4(),
        cluster_id=cluster.id,
        trend_velocity=trend_velocity,
        competitor_count=competitor_count,
        trend_match_count=trend_match_count,
        tempo_covered=tempo_covered,
        last_internal_days_ago=last_internal_days_ago,
        underperformed=underperformed,
    )
    return cluster, insight


async def test_morning_excludes_tempo_covered_cluster(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4())
    cluster, insight = _cluster_with_insight(run.id, tempo_covered=True)
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert str(cluster.id) not in ids


async def test_morning_includes_uncovered_cluster(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4())
    cluster, insight = _cluster_with_insight(run.id, tempo_covered=False)
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert str(cluster.id) in ids


async def test_morning_ordered_by_trend_velocity_desc(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4())
    c1, i1 = _cluster_with_insight(run.id, trend_velocity=0.9)
    c2, i2 = _cluster_with_insight(run.id, trend_velocity=0.2)
    c3, i3 = _cluster_with_insight(run.id, trend_velocity=0.6)
    session.add_all([run, c1, i1, c2, i2, c3, i3])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    data = response.json()
    ids = [r["id"] for r in data]
    # c1 (0.9) should come before c3 (0.6) which before c2 (0.2)
    assert ids.index(str(c1.id)) < ids.index(str(c3.id))
    assert ids.index(str(c3.id)) < ids.index(str(c2.id))


async def test_morning_respects_top_n(
    session: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    from core.config import settings as cfg

    monkeypatch.setattr(cfg, "scoring_morning_top_n", 2)

    run = ClusterRun(id=uuid.uuid4())
    clusters_insights = [_cluster_with_insight(run.id) for _ in range(5)]
    session.add(run)
    for c, i in clusters_insights:
        session.add_all([c, i])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    assert len(response.json()) <= 2


async def test_deferred_returns_high_velocity_uncovered_stale(
    session: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    from core.config import settings as cfg

    monkeypatch.setattr(cfg, "scoring_deferred_velocity_min", 0.4)
    monkeypatch.setattr(cfg, "scoring_recent_internal_days", 7)

    run = ClusterRun(id=uuid.uuid4())
    # qualifies: high velocity, uncovered, stale (14 days ago)
    c_yes, i_yes = _cluster_with_insight(
        run.id, trend_velocity=0.8, tempo_covered=False, last_internal_days_ago=14
    )
    # disqualified: covered
    c_covered, i_covered = _cluster_with_insight(
        run.id, trend_velocity=0.8, tempo_covered=True
    )
    # disqualified: low velocity
    c_slow, i_slow = _cluster_with_insight(
        run.id, trend_velocity=0.1, tempo_covered=False, last_internal_days_ago=14
    )
    session.add_all([run, c_yes, i_yes, c_covered, i_covered, c_slow, i_slow])
    await session.flush()

    response = await client.get("/api/v1/clusters/deferred")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert str(c_yes.id) in ids
    assert str(c_covered.id) not in ids
    assert str(c_slow.id) not in ids


async def test_cluster_detail_returns_new_schema(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4())
    cluster, insight = _cluster_with_insight(
        run.id,
        tempo_covered=True,
        trend_velocity=0.7,
        competitor_count=3,
        trend_match_count=2,
        last_internal_days_ago=5,
        underperformed=True,
    )
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get(f"/api/v1/clusters/{cluster.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["tempo_covered"] is True
    assert data["trend_velocity"] == pytest.approx(0.7)
    assert data["competitor_count"] == 3
    assert data["trend_match_count"] == 2
    assert data["last_internal_days_ago"] == 5
    assert data["underperformed"] is True
    assert "recommendation" not in data
    assert "novelty_score" not in data
    assert "coverage_score" not in data


async def test_cluster_detail_returns_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/clusters/{uuid.uuid4()}")
    assert response.status_code == 404
