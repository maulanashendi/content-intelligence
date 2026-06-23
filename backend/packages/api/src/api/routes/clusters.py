import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from core.config import settings
from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterInsight,
    ClusterRun,
    ClusterRunStage,
    ContentSource,
    SourceType,
)
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import exists, func, literal, or_, select
from sqlalchemy.orm import aliased

from api.deps import SessionDep
from api.types import UtcDateTime

router = APIRouter(prefix="/clusters", tags=["clusters"])


class ClusterSummary(BaseModel):
    id: uuid.UUID
    parent_cluster_id: uuid.UUID | None
    label: str | None
    member_count: int | None
    is_current: bool
    created_at: UtcDateTime
    trend_velocity: float | None
    competitor_count: int | None
    trend_match_count: int | None
    weighted_trend_score: float | None
    tempo_covered: bool | None
    last_internal_days_ago: int | None
    underperformed: bool | None
    competitor_freshness_days: int | None
    demand_score: float | None
    high_demand: bool | None
    performance_level: str | None
    editorial_quadrant: str | None
    what_happened: str | None
    parties_involved: list[str] | None
    editorial_angle: str | None
    bullet_insights: list[str] | None
    insight_calculated_at: UtcDateTime | None


class ClusterListResponse(BaseModel):
    clusters: list[ClusterSummary]
    served_at: UtcDateTime | None
    is_stale: bool
    max_age_hours: int


class BentoCard(BaseModel):
    id: uuid.UUID
    label: str | None
    editorial_quadrant: str | None
    trend_velocity: float | None
    competitor_count: int | None
    trend_match_count: int | None
    member_count: int | None
    views: int
    internal_article_count: int
    last_competitor_at: UtcDateTime | None
    last_internal_at: UtcDateTime | None


class BentoListResponse(BaseModel):
    cards: list[BentoCard]
    total: int
    served_at: UtcDateTime | None
    is_stale: bool
    max_age_hours: int


class ArticleSummary(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    first_paragraph: str | None
    published_at: UtcDateTime | None
    source_name: str
    relevance_score: float | None


class ClusterDetail(ClusterSummary):
    members: list[ArticleSummary]
    sub_clusters: list[ClusterSummary] | None
    parent_cluster: ClusterSummary | None
    sibling_clusters: list[ClusterSummary] | None
    is_stale: bool


class ClusterRunStageResponse(BaseModel):
    stage: str
    status: str
    started_at: UtcDateTime
    finished_at: UtcDateTime | None
    details: dict | None


class ClusterRunResponse(BaseModel):
    id: uuid.UUID
    algorithm: str | None
    algorithm_version: str | None
    params: dict | None
    started_at: UtcDateTime
    finished_at: UtcDateTime | None
    notes: str | None
    cluster_count: int
    has_insights: bool
    stages: list[ClusterRunStageResponse] = []


def _distinct(items: list[str] | None) -> list[str] | None:
    if not items:
        return items
    return list(dict.fromkeys(items))


def _to_summary(
    cluster: ArticleCluster, insight: ClusterInsight | None
) -> ClusterSummary:
    return ClusterSummary(
        id=cluster.id,
        parent_cluster_id=cluster.parent_cluster_id,
        label=cluster.label,
        member_count=cluster.member_count,
        is_current=cluster.is_current,
        created_at=cluster.created_at,
        trend_velocity=insight.trend_velocity if insight else None,
        competitor_count=insight.competitor_count if insight else None,
        trend_match_count=insight.trend_match_count if insight else None,
        weighted_trend_score=insight.weighted_trend_score if insight else None,
        tempo_covered=insight.tempo_covered if insight else None,
        last_internal_days_ago=insight.last_internal_days_ago if insight else None,
        underperformed=insight.underperformed if insight else None,
        competitor_freshness_days=insight.competitor_freshness_days if insight else None,
        demand_score=insight.demand_score if insight else None,
        high_demand=insight.high_demand if insight else None,
        performance_level=insight.performance_level if insight else None,
        editorial_quadrant=insight.editorial_quadrant if insight else None,
        what_happened=insight.what_happened if insight else None,
        parties_involved=_distinct(insight.parties_involved if insight else None),
        editorial_angle=insight.editorial_angle if insight else None,
        bullet_insights=_distinct(insight.summary if insight else None),
        insight_calculated_at=insight.calculated_at if insight else None,
    )


def _leaf_guard() -> object:
    child = aliased(ArticleCluster)
    return ~exists(
        select(literal(1))
        .where(child.parent_cluster_id == ArticleCluster.id)
        .correlate(ArticleCluster)
    )


def _ranking_order() -> list:
    """Shared ORDER BY for morning + bento so the two ranking surfaces cannot drift.

    The trailing ArticleCluster.id is a stable tiebreaker required for correct
    offset pagination on /bento.
    """
    return [
        (ClusterInsight.editorial_quadrant == "opportunity").desc(),
        ClusterInsight.demand_score.desc().nullslast(),
        ClusterInsight.trend_match_count.desc().nullslast(),
        ArticleCluster.member_count.desc().nullslast(),
        ArticleCluster.id,
    ]


def _resolve_cluster_filter() -> Any:
    """Return a WHERE clause for the most recent run that has completed scoring.

    Scoring (ClusterInsight upsert) happens after clustering and labeling.
    Without this guard, the window between ClusterRun.finished_at being set
    and scoring completing causes /morning and /deferred to return empty lists.
    """
    has_insights = exists(
        select(literal(1))
        .select_from(ArticleCluster)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(ArticleCluster.run_id == ClusterRun.id)
        .correlate(ClusterRun)
    )
    scored_run_id = (
        select(ClusterRun.id)
        .where(ClusterRun.finished_at.isnot(None))
        .where(has_insights)
        .order_by(ClusterRun.started_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    return ArticleCluster.run_id == scored_run_id


async def _get_served_at(session, run_filter) -> datetime | None:
    stmt = (
        select(func.max(ClusterInsight.calculated_at))
        .select_from(ArticleCluster)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(run_filter)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _compute_is_stale(served_at: datetime | None) -> bool:
    if served_at is None:
        return True
    now = datetime.now(UTC).replace(tzinfo=None)
    return (now - served_at) > timedelta(hours=settings.cluster_staleness_max_age_hours)


class QuadrantSummary(BaseModel):
    opportunity: int
    winning: int
    evergreen: int
    ignore: int
    too_early: int
    total: int


@router.get("/quadrant-summary", response_model=QuadrantSummary, summary="Quadrant distribution across all current clusters")
async def quadrant_summary(session: SessionDep) -> QuadrantSummary:
    run_filter = _resolve_cluster_filter()
    stmt = (
        select(
            ClusterInsight.editorial_quadrant,
            func.count().label("n"),
        )
        .select_from(ArticleCluster)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(run_filter, _leaf_guard())
        .group_by(ClusterInsight.editorial_quadrant)
    )
    rows = (await session.execute(stmt)).all()
    counts: dict[str, int] = {}
    for quadrant, n in rows:
        counts[quadrant or "ignore"] = n
    return QuadrantSummary(
        opportunity=counts.get("opportunity", 0),
        winning=counts.get("winning", 0),
        evergreen=counts.get("evergreen", 0),
        ignore=counts.get("ignore", 0),
        too_early=counts.get("too_early", 0),
        total=sum(counts.values()),
    )


_VALID_QUADRANTS = {"opportunity", "winning", "evergreen", "ignore", "too_early"}


@router.get("/quadrant/{quadrant}", response_model=ClusterListResponse, summary="Top clusters for a given editorial quadrant")
async def clusters_by_quadrant(
    quadrant: str,
    session: SessionDep,
    limit: int = Query(default=8, ge=1, le=50),
) -> ClusterListResponse:
    if quadrant not in _VALID_QUADRANTS:
        raise HTTPException(status_code=422, detail=f"quadrant must be one of {sorted(_VALID_QUADRANTS)}")
    run_filter = _resolve_cluster_filter()
    stmt = (
        select(ArticleCluster, ClusterInsight)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(
            run_filter,
            ClusterInsight.editorial_quadrant == quadrant,
            _leaf_guard(),
        )
        .order_by(
            ClusterInsight.demand_score.desc().nullslast(),
            ArticleCluster.member_count.desc().nullslast(),
        )
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    clusters = [_to_summary(cluster, insight) for cluster, insight in rows]
    served_at = await _get_served_at(session, run_filter)
    return ClusterListResponse(
        clusters=clusters,
        served_at=served_at,
        is_stale=_compute_is_stale(served_at),
        max_age_hours=settings.cluster_staleness_max_age_hours,
    )


@router.get("/morning", response_model=ClusterListResponse, summary="Morning briefing — opportunity clusters ranked by demand × performance")
async def morning_clusters(session: SessionDep) -> ClusterListResponse:
    run_filter = _resolve_cluster_filter()
    stmt = (
        select(ArticleCluster, ClusterInsight)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(
            run_filter,
            ClusterInsight.tempo_covered.is_(False),
            _leaf_guard(),
        )
        .order_by(*_ranking_order())
        .limit(settings.scoring_morning_top_n)
    )
    rows = (await session.execute(stmt)).all()
    clusters = [_to_summary(cluster, insight) for cluster, insight in rows]
    served_at = await _get_served_at(session, run_filter)
    return ClusterListResponse(
        clusters=clusters,
        served_at=served_at,
        is_stale=_compute_is_stale(served_at),
        max_age_hours=settings.cluster_staleness_max_age_hours,
    )


@router.get("/bento", response_model=BentoListResponse, summary="All current clusters ranked, paginated, for the bento card grid")
async def bento_clusters(
    session: SessionDep,
    limit: int = Query(default=8, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> BentoListResponse:
    run_filter = _resolve_cluster_filter()
    base_where = (run_filter, _leaf_guard())

    total: int = (
        await session.execute(
            select(func.count())
            .select_from(ArticleCluster)
            .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
            .where(*base_where)
        )
    ).scalar_one()

    rows = (
        await session.execute(
            select(ArticleCluster, ClusterInsight)
            .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
            .where(*base_where)
            .order_by(*_ranking_order())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    page_ids = [cluster.id for cluster, _ in rows]
    enrich: dict[uuid.UUID, Any] = {}
    if page_ids:
        effective = func.coalesce(Article.published_at, Article.created_at)
        enrich_rows = (
            await session.execute(
                select(
                    ArticleClusterMember.cluster_id.label("cid"),
                    func.count()
                    .filter(ContentSource.source_type == SourceType.internal)
                    .label("internal_count"),
                    func.max(effective)
                    .filter(ContentSource.source_type == SourceType.rss)
                    .label("last_competitor_at"),
                    func.max(effective)
                    .filter(ContentSource.source_type == SourceType.internal)
                    .label("last_internal_at"),
                )
                .select_from(ArticleClusterMember)
                .join(Article, Article.id == ArticleClusterMember.article_id)
                .join(ContentSource, ContentSource.id == Article.source_id)
                .where(ArticleClusterMember.cluster_id.in_(page_ids))
                .group_by(ArticleClusterMember.cluster_id)
            )
        ).all()
        enrich = {r.cid: r for r in enrich_rows}

    cards = [
        BentoCard(
            id=cluster.id,
            label=cluster.label,
            editorial_quadrant=insight.editorial_quadrant,
            trend_velocity=insight.trend_velocity,
            competitor_count=insight.competitor_count,
            trend_match_count=insight.trend_match_count,
            member_count=cluster.member_count,
            views=insight.gsc_clicks,
            internal_article_count=(enrich[cluster.id].internal_count if cluster.id in enrich else 0),
            last_competitor_at=(enrich[cluster.id].last_competitor_at if cluster.id in enrich else None),
            last_internal_at=(enrich[cluster.id].last_internal_at if cluster.id in enrich else None),
        )
        for cluster, insight in rows
    ]
    served_at = await _get_served_at(session, run_filter)
    return BentoListResponse(
        cards=cards,
        total=total,
        served_at=served_at,
        is_stale=_compute_is_stale(served_at),
        max_age_hours=settings.cluster_staleness_max_age_hours,
    )


@router.get("/deferred", response_model=ClusterListResponse, summary="Deferred clusters — high demand, uncovered, stale internal coverage")
async def deferred_clusters(session: SessionDep) -> ClusterListResponse:
    run_filter = _resolve_cluster_filter()
    stmt = (
        select(ArticleCluster, ClusterInsight)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(
            run_filter,
            ClusterInsight.high_demand.is_(True),
            ClusterInsight.tempo_covered.is_(False),
            or_(
                ClusterInsight.last_internal_days_ago.is_(None),
                ClusterInsight.last_internal_days_ago
                > settings.scoring_recent_internal_days,
            ),
            _leaf_guard(),
        )
        .order_by(
            ClusterInsight.demand_score.desc().nullslast(),
            ClusterInsight.trend_velocity.desc().nullslast(),
        )
    )
    rows = (await session.execute(stmt)).all()
    clusters = [_to_summary(cluster, insight) for cluster, insight in rows]
    served_at = await _get_served_at(session, run_filter)
    return ClusterListResponse(
        clusters=clusters,
        served_at=served_at,
        is_stale=_compute_is_stale(served_at),
        max_age_hours=settings.cluster_staleness_max_age_hours,
    )


@router.get("/runs/latest", response_model=ClusterRunResponse)
async def latest_cluster_run(session: SessionDep) -> ClusterRunResponse:
    run_has_insights = exists(
        select(literal(1))
        .select_from(ArticleCluster)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(ArticleCluster.run_id == ClusterRun.id)
        .correlate(ClusterRun)
    ).label("has_insights")
    stmt = (
        select(
            ClusterRun,
            func.count(ArticleCluster.id).label("cluster_count"),
            run_has_insights,
        )
        .outerjoin(
            ArticleCluster,
            (ArticleCluster.run_id == ClusterRun.id) & ArticleCluster.is_current.is_(True),
        )
        .group_by(ClusterRun.id)
        .order_by(ClusterRun.started_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No cluster run found")
    run, cluster_count, has_insights = row

    stage_rows = (
        await session.execute(
            select(ClusterRunStage)
            .where(ClusterRunStage.run_id == run.id)
            .order_by(ClusterRunStage.started_at)
        )
    ).scalars().all()
    stages = [
        ClusterRunStageResponse(
            stage=s.stage.value,
            status=s.status.value,
            started_at=s.started_at,
            finished_at=s.finished_at,
            details=s.details,
        )
        for s in stage_rows
    ]

    return ClusterRunResponse(
        id=run.id,
        algorithm=run.algorithm.value if run.algorithm else None,
        algorithm_version=run.algorithm_version,
        params=run.params,
        started_at=run.started_at,
        finished_at=run.finished_at,
        notes=run.notes,
        cluster_count=cluster_count,
        has_insights=bool(has_insights),
        stages=stages,
    )


@router.get("/current", response_model=ClusterListResponse, summary="All clusters in the current scored run")
async def current_clusters(
    session: SessionDep,
    order: Literal["asc", "desc"] = Query(default="desc"),
) -> ClusterListResponse:
    run_filter = _resolve_cluster_filter()
    sort_col = (
        ArticleCluster.member_count.asc().nullslast()
        if order == "asc"
        else ArticleCluster.member_count.desc().nullslast()
    )
    stmt = (
        select(ArticleCluster, ClusterInsight)
        .outerjoin(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(run_filter)
        .order_by(sort_col)
    )
    rows = (await session.execute(stmt)).all()
    clusters = [_to_summary(cluster, insight) for cluster, insight in rows]
    served_at = await _get_served_at(session, run_filter)
    return ClusterListResponse(
        clusters=clusters,
        served_at=served_at,
        is_stale=_compute_is_stale(served_at),
        max_age_hours=settings.cluster_staleness_max_age_hours,
    )


@router.get("/{cluster_id}", response_model=ClusterDetail, summary="Full detail for a single cluster")
async def cluster_detail(cluster_id: uuid.UUID, session: SessionDep) -> ClusterDetail:
    cluster_stmt = (
        select(ArticleCluster, ClusterInsight)
        .outerjoin(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(ArticleCluster.id == cluster_id)
    )
    row = (await session.execute(cluster_stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Cluster not found")

    cluster, insight = row

    members_stmt = (
        select(
            Article.id,
            Article.title,
            Article.url,
            Article.first_paragraph,
            Article.published_at,
            ContentSource.name.label("source_name"),
            ArticleClusterMember.relevance_score,
        )
        .select_from(ArticleClusterMember)
        .join(Article, Article.id == ArticleClusterMember.article_id)
        .join(ContentSource, ContentSource.id == Article.source_id)
        .where(ArticleClusterMember.cluster_id == cluster_id)
        .order_by(ArticleClusterMember.relevance_score.desc().nullslast())
    )
    member_rows = (await session.execute(members_stmt)).all()

    members = [
        ArticleSummary(
            id=r.id,
            title=r.title,
            url=r.url,
            first_paragraph=r.first_paragraph,
            published_at=r.published_at,
            source_name=r.source_name,
            relevance_score=r.relevance_score,
        )
        for r in member_rows
    ]

    sub_clusters_stmt = (
        select(ArticleCluster, ClusterInsight)
        .outerjoin(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(ArticleCluster.parent_cluster_id == cluster_id)
        .order_by(ArticleCluster.member_count.desc().nullslast())
    )
    sub_rows = (await session.execute(sub_clusters_stmt)).all()
    sub_clusters = [_to_summary(c, i) for c, i in sub_rows] or None

    parent_cluster_summary = None
    sibling_clusters = None
    if cluster.parent_cluster_id is not None:
        parent_stmt = (
            select(ArticleCluster, ClusterInsight)
            .outerjoin(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
            .where(ArticleCluster.id == cluster.parent_cluster_id)
        )
        parent_row = (await session.execute(parent_stmt)).one_or_none()
        if parent_row:
            parent_cluster_summary = _to_summary(*parent_row)

        sibling_stmt = (
            select(ArticleCluster, ClusterInsight)
            .outerjoin(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
            .where(
                ArticleCluster.parent_cluster_id == cluster.parent_cluster_id,
                ArticleCluster.id != cluster_id,
            )
            .order_by(ArticleCluster.member_count.desc().nullslast())
            .limit(10)
        )
        sibling_rows = (await session.execute(sibling_stmt)).all()
        sibling_clusters = [_to_summary(c, i) for c, i in sibling_rows] or None

    base = _to_summary(cluster, insight)
    return ClusterDetail(
        **base.model_dump(),
        members=members,
        sub_clusters=sub_clusters,
        parent_cluster=parent_cluster_summary,
        sibling_clusters=sibling_clusters,
        is_stale=_compute_is_stale(insight.calculated_at if insight else None),
    )
