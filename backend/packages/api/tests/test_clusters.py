import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

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
_OLDER = _NOW - timedelta(days=1)


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
    weighted_trend_score: float | None = None,
    last_internal_days_ago: int | None = None,
    underperformed: bool = False,
    demand_score: float | None = None,
    high_demand: bool | None = None,
    performance_level: str | None = None,
    editorial_quadrant: str | None = None,
    what_happened: str | None = None,
    parties_involved: list[str] | None = None,
    editorial_angle: str | None = None,
    summary: list[str] | None = None,
    parent_cluster_id: uuid.UUID | None = None,
) -> tuple[ArticleCluster, ClusterInsight]:
    cluster = ArticleCluster(
        id=uuid.uuid4(),
        run_id=run_id,
        label="Test",
        is_current=True,
        parent_cluster_id=parent_cluster_id,
    )
    insight = ClusterInsight(
        id=uuid.uuid4(),
        cluster_id=cluster.id,
        trend_velocity=trend_velocity,
        competitor_count=competitor_count,
        trend_match_count=trend_match_count,
        weighted_trend_score=weighted_trend_score,
        tempo_covered=tempo_covered,
        last_internal_days_ago=last_internal_days_ago,
        underperformed=underperformed,
        demand_score=demand_score,
        high_demand=high_demand,
        performance_level=performance_level,
        editorial_quadrant=editorial_quadrant,
        what_happened=what_happened,
        parties_involved=parties_involved,
        editorial_angle=editorial_angle,
        summary=summary,
    )
    return cluster, insight


async def test_morning_excludes_tempo_covered_cluster(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(run.id, tempo_covered=True)
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert str(cluster.id) not in ids


async def test_morning_includes_uncovered_cluster(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(run.id, tempo_covered=False)
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert str(cluster.id) in ids


async def test_morning_prioritizes_opportunity_quadrant_then_demand_score(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    # opportunity with high demand_score — should rank first
    c1, i1 = _cluster_with_insight(
        run.id,
        editorial_quadrant="opportunity",
        demand_score=0.9,
        high_demand=True,
        performance_level="none",
    )
    # opportunity with lower demand_score
    c2, i2 = _cluster_with_insight(
        run.id,
        editorial_quadrant="opportunity",
        demand_score=0.5,
        high_demand=True,
        performance_level="none",
    )
    # ignore quadrant — sinks to bottom even with high trend_match_count
    c3, i3 = _cluster_with_insight(
        run.id,
        editorial_quadrant="ignore",
        demand_score=0.0,
        high_demand=False,
        performance_level="none",
        trend_match_count=5,
    )
    session.add_all([run, c1, i1, c2, i2, c3, i3])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert ids.index(str(c1.id)) < ids.index(str(c2.id))
    assert ids.index(str(c2.id)) < ids.index(str(c3.id))


async def test_morning_respects_top_n(
    session: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    from core.config import settings as cfg

    monkeypatch.setattr(cfg, "scoring_morning_top_n", 2)

    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    clusters_insights = [_cluster_with_insight(run.id) for _ in range(5)]
    session.add(run)
    for c, i in clusters_insights:
        session.add_all([c, i])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    assert len(response.json()["clusters"]) <= 2


async def test_deferred_returns_high_demand_uncovered_stale(
    session: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    from core.config import settings as cfg

    monkeypatch.setattr(cfg, "scoring_recent_internal_days", 7)

    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    # qualifies: high_demand, uncovered, stale (14 days ago)
    c_yes, i_yes = _cluster_with_insight(
        run.id, high_demand=True, tempo_covered=False, last_internal_days_ago=14
    )
    # disqualified: covered
    c_covered, i_covered = _cluster_with_insight(
        run.id, high_demand=True, tempo_covered=True
    )
    # disqualified: not high_demand
    c_slow, i_slow = _cluster_with_insight(
        run.id, high_demand=False, tempo_covered=False, last_internal_days_ago=14
    )
    session.add_all([run, c_yes, i_yes, c_covered, i_covered, c_slow, i_slow])
    await session.flush()

    response = await client.get("/api/v1/clusters/deferred")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert str(c_yes.id) in ids
    assert str(c_covered.id) not in ids
    assert str(c_slow.id) not in ids


async def test_cluster_detail_returns_new_schema(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
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


async def test_cluster_detail_exposes_insight_fields(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(
        run.id,
        demand_score=0.75,
        high_demand=True,
        performance_level="low",
        editorial_quadrant="opportunity",
        what_happened="Terjadi sesuatu penting.",
        parties_involved=["Pihak A", "Pihak B", "Pihak A"],
        editorial_angle="Sudut editorial yang menarik.",
        summary=["Klaim satu", "Klaim dua", "Klaim satu"],
    )
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get(f"/api/v1/clusters/{cluster.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["demand_score"] == pytest.approx(0.75)
    assert data["high_demand"] is True
    assert data["performance_level"] == "low"
    assert data["editorial_quadrant"] == "opportunity"
    assert data["what_happened"] == "Terjadi sesuatu penting."
    assert data["editorial_angle"] == "Sudut editorial yang menarik."
    # distinct applied — duplicates removed, order preserved
    assert data["parties_involved"] == ["Pihak A", "Pihak B"]
    assert data["bullet_insights"] == ["Klaim satu", "Klaim dua"]
    assert data["parent_cluster"] is None
    assert data["sibling_clusters"] is None
    # raw GSC fields must not be in the response (D35)
    assert "tempo_gsc_impressions" not in data
    assert "gsc_demand_gap" not in data


async def test_cluster_detail_returns_parent_and_siblings(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    parent, parent_insight = _cluster_with_insight(run.id)
    child, child_insight = _cluster_with_insight(run.id, parent_cluster_id=parent.id)
    sibling, sibling_insight = _cluster_with_insight(run.id, parent_cluster_id=parent.id)
    session.add_all([run, parent, parent_insight, child, child_insight, sibling, sibling_insight])
    await session.flush()

    response = await client.get(f"/api/v1/clusters/{child.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["parent_cluster"] is not None
    assert data["parent_cluster"]["id"] == str(parent.id)
    assert data["sibling_clusters"] is not None
    sibling_ids = [s["id"] for s in data["sibling_clusters"]]
    assert str(sibling.id) in sibling_ids
    assert str(child.id) not in sibling_ids


async def test_cluster_detail_returns_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/clusters/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_run_without_finished_at_is_never_shown(
    session: AsyncSession, client: AsyncClient
) -> None:
    """A ClusterRun without finished_at (clustering still writing) is skipped."""
    run = ClusterRun(id=uuid.uuid4(), finished_at=None)
    cluster, insight = _cluster_with_insight(run.id)
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert str(cluster.id) not in ids


async def test_no_ready_run_returns_empty(client: AsyncClient) -> None:
    """With no qualifying run the endpoint returns an empty envelope, not an error."""
    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    data = response.json()
    assert data["clusters"] == []
    assert data["is_stale"] is True
    assert data["served_at"] is None


async def test_morning_falls_back_to_previous_run_when_new_run_unscored(
    session: AsyncSession, client: AsyncClient
) -> None:
    """New run finished clustering but scoring not yet done → fall back to previous run data."""
    old_run = ClusterRun(id=uuid.uuid4(), finished_at=_OLDER)
    old_cluster, old_insight = _cluster_with_insight(old_run.id, tempo_covered=False)

    new_run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    new_cluster = ArticleCluster(id=uuid.uuid4(), run_id=new_run.id, label="New", is_current=True)

    session.add_all([old_run, old_cluster, old_insight, new_run, new_cluster])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert str(old_cluster.id) in ids
    assert str(new_cluster.id) not in ids


async def test_runs_latest_has_insights_true_when_scored(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(run.id)
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/runs/latest")
    assert response.status_code == 200
    assert response.json()["has_insights"] is True


async def test_runs_latest_has_insights_false_when_unscored(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, label="Test", is_current=True)
    session.add_all([run, cluster])
    await session.flush()

    response = await client.get("/api/v1/clusters/runs/latest")
    assert response.status_code == 200
    assert response.json()["has_insights"] is False


async def test_morning_is_stale_when_insight_too_old(
    session: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    from core.config import settings as cfg

    monkeypatch.setattr(cfg, "cluster_staleness_max_age_hours", 36)

    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(run.id, tempo_covered=False)
    insight.calculated_at = _NOW - timedelta(hours=48)
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    data = response.json()
    assert data["is_stale"] is True
    assert data["served_at"] is not None
    assert data["max_age_hours"] == 36


async def test_morning_is_not_stale_when_insight_recent(
    session: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    from core.config import settings as cfg

    monkeypatch.setattr(cfg, "cluster_staleness_max_age_hours", 36)

    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(run.id, tempo_covered=False)
    insight.calculated_at = _NOW - timedelta(hours=1)
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    data = response.json()
    assert data["is_stale"] is False
    assert data["served_at"] is not None
