import uuid
from datetime import UTC, datetime, timedelta

from core.models import ArticleCluster, ClusterInsight, ClusterRun
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)

_RAW_GSC_FIELDS = ("tempo_gsc_impressions", "gsc_demand_gap", "gsc_impressions", "gsc_clicks", "gsc_ctr", "gsc_avg_position")
_EDITORIAL_FIELDS = ("demand_score", "high_demand", "performance_level", "editorial_quadrant")


def _cluster_with_gsc(run_id: uuid.UUID) -> tuple[ArticleCluster, ClusterInsight]:
    """Uncovered cluster with demand/performance insight values set."""
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_id, label="Test", is_current=True)
    insight = ClusterInsight(
        id=uuid.uuid4(),
        cluster_id=cluster.id,
        trend_velocity=0.9,
        competitor_count=3,
        trend_match_count=2,
        tempo_covered=False,
        last_internal_days_ago=40,
        underperformed=True,
        demand_score=0.8,
        high_demand=True,
        performance_level="none",
        editorial_quadrant="opportunity",
    )
    return cluster, insight


async def test_raw_gsc_never_returned_editorial_levels_are(
    session: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    """D35: raw GSC numbers never appear in API responses; derived editorial
    levels (demand_score, high_demand, performance_level, editorial_quadrant) do.
    """
    from core.config import settings as cfg

    monkeypatch.setattr(cfg, "scoring_deferred_velocity_min", 0.4)
    monkeypatch.setattr(cfg, "scoring_recent_internal_days", 7)

    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_gsc(run.id)
    session.add_all([run, cluster, insight])
    await session.flush()

    list_paths = [
        "/api/v1/clusters/morning",
        "/api/v1/clusters/current",
        "/api/v1/clusters/deferred",
        "/api/v1/clusters/bento",
    ]
    for path in list_paths:
        response = await client.get(path)
        assert response.status_code == 200, path
        for field in _RAW_GSC_FIELDS:
            assert field not in response.text, f"raw GSC field {field} leaked by {path}"

    # D38: bento exposes aggregated clicks as `views` (never the raw `gsc_clicks` name).
    bento = (await client.get("/api/v1/clusters/bento")).json()
    assert bento["cards"], "expected the seeded cluster as a bento card"
    assert "views" in bento["cards"][0]

    detail = await client.get(f"/api/v1/clusters/{cluster.id}")
    assert detail.status_code == 200
    body = detail.json()
    for field in _RAW_GSC_FIELDS:
        assert field not in body, f"raw GSC field {field} leaked by cluster detail"
    for field in _EDITORIAL_FIELDS:
        assert field in body, f"editorial field {field} missing from cluster detail"
