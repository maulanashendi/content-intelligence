import uuid
from datetime import UTC, datetime, timedelta

from core.models import ArticleCluster, ClusterInsight, ClusterRun
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)

_GSC_FIELDS = ("tempo_gsc_impressions", "gsc_demand_gap")


def _cluster_with_gsc(run_id: uuid.UUID) -> tuple[ArticleCluster, ClusterInsight]:
    """An uncovered cluster whose insight carries non-zero raw GSC values in the DB."""
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
        tempo_gsc_impressions=12345,
        gsc_demand_gap=True,
    )
    return cluster, insight


async def test_gsc_fields_never_returned_by_any_cluster_endpoint(
    session: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    """D7: raw GSC metrics are scoring inputs only — never serialized to the API.

    Populates the insight with non-zero GSC values, then asserts none of the read
    endpoints leak them. Fails if either field is reintroduced to the response model.
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
    ]
    for path in list_paths:
        response = await client.get(path)
        assert response.status_code == 200, path
        for field in _GSC_FIELDS:
            assert field not in response.text, f"{field} leaked by {path}"

    detail = await client.get(f"/api/v1/clusters/{cluster.id}")
    assert detail.status_code == 200
    body = detail.json()
    for field in _GSC_FIELDS:
        assert field not in body, f"{field} leaked by cluster detail"
        assert field not in detail.text
