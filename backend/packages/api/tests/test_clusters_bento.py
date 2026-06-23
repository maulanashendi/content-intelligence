import uuid
from datetime import UTC, datetime, timedelta

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
        title="Test Article",
        url=f"https://test-{uuid.uuid4()}.com/a",
        published_at=published_at,
    )


def _cluster_insight(
    run_id: uuid.UUID,
    *,
    tempo_covered: bool = False,
    editorial_quadrant: str | None = "opportunity",
    demand_score: float | None = 0.5,
    gsc_clicks: int = 0,
    member_count: int | None = 1,
) -> tuple[ArticleCluster, ClusterInsight]:
    cluster = ArticleCluster(
        id=uuid.uuid4(),
        run_id=run_id,
        label="Test",
        is_current=True,
        member_count=member_count,
    )
    insight = ClusterInsight(
        id=uuid.uuid4(),
        cluster_id=cluster.id,
        trend_velocity=0.5,
        competitor_count=2,
        trend_match_count=1,
        tempo_covered=tempo_covered,
        editorial_quadrant=editorial_quadrant,
        demand_score=demand_score,
        gsc_clicks=gsc_clicks,
    )
    return cluster, insight


async def test_bento_includes_all_quadrants_unlike_morning(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    covered, covered_i = _cluster_insight(
        run.id, tempo_covered=True, editorial_quadrant="winning"
    )
    session.add_all([run, covered, covered_i])
    await session.flush()

    bento_ids = [c["id"] for c in (await client.get("/api/v1/clusters/bento")).json()["cards"]]
    morning_ids = [c["id"] for c in (await client.get("/api/v1/clusters/morning")).json()["clusters"]]
    assert str(covered.id) in bento_ids
    assert str(covered.id) not in morning_ids


async def test_bento_ranks_opportunity_then_demand(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    c1, i1 = _cluster_insight(run.id, editorial_quadrant="opportunity", demand_score=0.9)
    c2, i2 = _cluster_insight(run.id, editorial_quadrant="opportunity", demand_score=0.5)
    c3, i3 = _cluster_insight(run.id, editorial_quadrant="ignore", demand_score=0.0)
    session.add_all([run, c1, i1, c2, i2, c3, i3])
    await session.flush()

    ids = [c["id"] for c in (await client.get("/api/v1/clusters/bento")).json()["cards"]]
    assert ids.index(str(c1.id)) < ids.index(str(c2.id)) < ids.index(str(c3.id))


async def test_bento_pagination_offset_limit_and_total(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    items = []
    # Distinct demand_score => fully deterministic order, highest first.
    for n in range(5):
        c, i = _cluster_insight(run.id, demand_score=0.9 - n * 0.1)
        items += [c, i]
    session.add_all([run, *items])
    await session.flush()

    page1 = (await client.get("/api/v1/clusters/bento?limit=2&offset=0")).json()
    page2 = (await client.get("/api/v1/clusters/bento?limit=2&offset=2")).json()
    assert page1["total"] == 5
    assert len(page1["cards"]) == 2
    assert len(page2["cards"]) == 2
    p1_ids = {c["id"] for c in page1["cards"]}
    p2_ids = {c["id"] for c in page2["cards"]}
    assert p1_ids.isdisjoint(p2_ids)


async def test_bento_exposes_views_from_gsc_clicks(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_insight(run.id, gsc_clicks=1234)
    session.add_all([run, cluster, insight])
    await session.flush()

    card = (await client.get("/api/v1/clusters/bento")).json()["cards"][0]
    assert card["views"] == 1234


async def test_bento_internal_count_and_timestamps(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_insight(run.id, member_count=3)
    rss = _source(SourceType.rss, "Kompas")
    internal = _source(SourceType.internal, "Tempo")
    comp_old = _article(rss.id, _NOW - timedelta(hours=10))
    comp_new = _article(rss.id, _NOW - timedelta(hours=2))
    internal_a = _article(internal.id, _NOW - timedelta(hours=5))
    session.add_all([run, cluster, insight, rss, internal, comp_old, comp_new, internal_a])
    await session.flush()
    session.add_all([
        ArticleClusterMember(cluster_id=cluster.id, article_id=comp_old.id),
        ArticleClusterMember(cluster_id=cluster.id, article_id=comp_new.id),
        ArticleClusterMember(cluster_id=cluster.id, article_id=internal_a.id),
    ])
    await session.flush()

    card = (await client.get("/api/v1/clusters/bento")).json()["cards"][0]
    assert card["internal_article_count"] == 1
    assert card["last_competitor_at"] is not None
    assert card["last_internal_at"] is not None
    # last_competitor_at is the newer of the two competitor articles
    assert card["last_competitor_at"] > card["last_internal_at"]


async def test_bento_zero_members_defaults(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_insight(run.id)
    session.add_all([run, cluster, insight])
    await session.flush()

    card = (await client.get("/api/v1/clusters/bento")).json()["cards"][0]
    assert card["internal_article_count"] == 0
    assert card["last_competitor_at"] is None
    assert card["last_internal_at"] is None


async def test_bento_empty_when_no_run(client: AsyncClient) -> None:
    data = (await client.get("/api/v1/clusters/bento")).json()
    assert data["cards"] == []
    assert data["total"] == 0
    assert data["is_stale"] is True
