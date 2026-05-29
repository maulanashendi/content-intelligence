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
    ContentSource,
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
    what_happened: str | None
    parties_involved: list[str] | None
    editorial_angle: str | None
    insight_calculated_at: UtcDateTime | None


class ClusterListResponse(BaseModel):
    clusters: list[ClusterSummary]
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
    is_stale: bool


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
        what_happened=insight.what_happened if insight else None,
        parties_involved=insight.parties_involved if insight else None,
        editorial_angle=insight.editorial_angle if insight else None,
        insight_calculated_at=insight.calculated_at if insight else None,
    )


def _leaf_guard() -> object:
    child = aliased(ArticleCluster)
    return ~exists(
        select(literal(1))
        .where(child.parent_cluster_id == ArticleCluster.id)
        .correlate(ArticleCluster)
    )


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


@router.get("/morning", response_model=ClusterListResponse, summary="Morning briefing — top uncovered clusters")
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
        .order_by(ClusterInsight.trend_velocity.desc().nullslast())
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


@router.get("/deferred", response_model=ClusterListResponse, summary="Deferred clusters — high velocity, uncovered, stale internal coverage")
async def deferred_clusters(session: SessionDep) -> ClusterListResponse:
    run_filter = _resolve_cluster_filter()
    stmt = (
        select(ArticleCluster, ClusterInsight)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(
            run_filter,
            ClusterInsight.trend_velocity > settings.scoring_deferred_velocity_min,
            ClusterInsight.tempo_covered.is_(False),
            or_(
                ClusterInsight.last_internal_days_ago.is_(None),
                ClusterInsight.last_internal_days_ago
                > settings.scoring_recent_internal_days,
            ),
            _leaf_guard(),
        )
        .order_by(ClusterInsight.trend_velocity.desc().nullslast())
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

    return ClusterDetail(
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
        what_happened=insight.what_happened if insight else None,
        parties_involved=insight.parties_involved if insight else None,
        editorial_angle=insight.editorial_angle if insight else None,
        insight_calculated_at=insight.calculated_at if insight else None,
        is_stale=_compute_is_stale(insight.calculated_at if insight else None),
        members=members,
        sub_clusters=sub_clusters,
    )
