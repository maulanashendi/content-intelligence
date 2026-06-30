"""Tests that verify /clusters endpoints return the label field.

The cluster map was showing IDs instead of names because article_cluster.label
was NULL. These tests fail when labeling never runs or skips all clusters.
"""

import uuid
from datetime import UTC, datetime

import pytest
from core.models import ArticleCluster, ClusterInsight, ClusterRun
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _run() -> ClusterRun:
    return ClusterRun(id=uuid.uuid4(), finished_at=_NOW)


def _cluster(run_id: uuid.UUID, *, label: str | None) -> ArticleCluster:
    return ArticleCluster(
        id=uuid.uuid4(),
        run_id=run_id,
        label=label,
        is_current=True,
        member_count=5,
    )


def _insight(cluster_id: uuid.UUID) -> ClusterInsight:
    return ClusterInsight(
        id=uuid.uuid4(),
        cluster_id=cluster_id,
        trend_velocity=0.5,
        competitor_count=2,
        trend_match_count=1,
        tempo_covered=False,
        underperformed=False,
        desk_category="Politik",
        user_need_category="Update me",
    )


async def test_morning_endpoint_returns_label(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = _run()
    cluster = _cluster(run.id, label="Harga Beras Naik Tajam")
    insight = _insight(cluster.id)
    session.add_all([run, cluster, insight])
    await session.flush()

    resp = await client.get("/api/v1/clusters/morning")
    assert resp.status_code == 200

    data = resp.json()["clusters"]
    ids = [r["id"] for r in data]
    assert str(cluster.id) in ids

    matched = next(r for r in data if r["id"] == str(cluster.id))
    assert matched["label"] == "Harga Beras Naik Tajam", (
        "API must return the cluster label, not the ID — "
        "if this fails, labeling pipeline did not write labels to the DB"
    )


async def test_cluster_detail_returns_label(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = _run()
    cluster = _cluster(run.id, label="Kenaikan Suku Bunga BI")
    insight = _insight(cluster.id)
    session.add_all([run, cluster, insight])
    await session.flush()

    resp = await client.get(f"/api/v1/clusters/{cluster.id}")
    assert resp.status_code == 200
    assert resp.json()["label"] == "Kenaikan Suku Bunga BI"


async def test_cluster_detail_null_label_is_null_not_id(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = _run()
    cluster = _cluster(run.id, label=None)
    insight = _insight(cluster.id)
    session.add_all([run, cluster, insight])
    await session.flush()

    resp = await client.get(f"/api/v1/clusters/{cluster.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] is None
    assert data["id"] != data.get("label"), "label must be null, not the cluster id"
