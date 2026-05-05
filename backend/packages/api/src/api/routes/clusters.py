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
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from api.deps import SessionDep
from api.types import UtcDateTime

router = APIRouter(prefix="/clusters", tags=["clusters"])


class ClusterSummary(BaseModel):
    id: uuid.UUID
    label: str | None
    member_count: int | None
    is_current: bool
    created_at: UtcDateTime
    trend_velocity: float | None
    novelty_score: float | None
    coverage_score: float | None
    recommendation: str | None
    summary: str | None
    insight_calculated_at: UtcDateTime | None


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


class ClusterRunResponse(BaseModel):
    id: uuid.UUID
    algorithm: str | None
    algorithm_version: str | None
    params: dict | None
    started_at: UtcDateTime
    finished_at: UtcDateTime | None
    notes: str | None
    cluster_count: int


def _to_summary(cluster: ArticleCluster, insight: ClusterInsight | None) -> ClusterSummary:
    return ClusterSummary(
        id=cluster.id,
        label=cluster.label,
        member_count=cluster.member_count,
        is_current=cluster.is_current,
        created_at=cluster.created_at,
        trend_velocity=insight.trend_velocity if insight else None,
        novelty_score=insight.novelty_score if insight else None,
        coverage_score=insight.coverage_score if insight else None,
        recommendation=insight.recommendation.value if insight and insight.recommendation else None,
        summary=insight.summary if insight else None,
        insight_calculated_at=insight.calculated_at if insight else None,
    )


@router.get("/morning", response_model=list[ClusterSummary])
async def morning_clusters(session: SessionDep) -> list[ClusterSummary]:
    thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).replace(tzinfo=None)

    # Exclude clusters where Tempo already published an article on this topic recently.
    has_internal_recent = (
        select(ArticleClusterMember.cluster_id)
        .join(Article, Article.id == ArticleClusterMember.article_id)
        .join(ContentSource, ContentSource.id == Article.source_id)
        .where(
            ArticleClusterMember.cluster_id == ArticleCluster.id,
            ContentSource.source_type == SourceType.internal,
            Article.published_at >= thirty_days_ago,
        )
        .correlate(ArticleCluster)
        .exists()
    )

    stmt = (
        select(ArticleCluster)
        .where(
            ArticleCluster.is_current.is_(True),
            ~has_internal_recent,
        )
        .order_by(ArticleCluster.member_count.desc().nullslast())
        .limit(10)
    )

    rows = (await session.execute(stmt)).scalars().all()
    return [_to_summary(cluster, None) for cluster in rows]


@router.get("/deferred", response_model=list[ClusterSummary])
async def deferred_clusters(session: SessionDep) -> list[ClusterSummary]:
    stmt = (
        select(ArticleCluster, ClusterInsight)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(
            ArticleCluster.is_current.is_(True),
            ClusterInsight.recommendation == InsightRecommendation.saturated,
        )
        .order_by(ClusterInsight.trend_velocity.desc().nullslast())
    )

    rows = (await session.execute(stmt)).all()
    return [_to_summary(cluster, insight) for cluster, insight in rows]


@router.get("/runs/latest", response_model=ClusterRunResponse)
async def latest_cluster_run(session: SessionDep) -> ClusterRunResponse:
    stmt = (
        select(
            ClusterRun,
            func.count(ArticleCluster.id).label("cluster_count"),
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
    run, cluster_count = row
    return ClusterRunResponse(
        id=run.id,
        algorithm=run.algorithm.value if run.algorithm else None,
        algorithm_version=run.algorithm_version,
        params=run.params,
        started_at=run.started_at,
        finished_at=run.finished_at,
        notes=run.notes,
        cluster_count=cluster_count,
    )


@router.get("/current", response_model=list[ClusterSummary])
async def current_clusters(
    session: SessionDep,
    order: Literal["asc", "desc"] = Query(default="desc"),
) -> list[ClusterSummary]:
    sort_col = (
        ArticleCluster.member_count.asc().nullslast()
        if order == "asc"
        else ArticleCluster.member_count.desc().nullslast()
    )
    stmt = (
        select(ArticleCluster, ClusterInsight)
        .outerjoin(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(ArticleCluster.is_current.is_(True))
        .order_by(sort_col)
    )
    rows = (await session.execute(stmt)).all()
    return [_to_summary(cluster, insight) for cluster, insight in rows]


@router.get("/{cluster_id}", response_model=ClusterDetail)
async def cluster_detail(cluster_id: uuid.UUID, session: SessionDep) -> ClusterDetail:
    cluster_stmt = (
        select(ArticleCluster, ClusterInsight)
        .outerjoin(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(ArticleCluster.id == cluster_id, ArticleCluster.is_current.is_(True))
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

    return ClusterDetail(
        id=cluster.id,
        label=cluster.label,
        member_count=cluster.member_count,
        is_current=cluster.is_current,
        created_at=cluster.created_at,
        trend_velocity=insight.trend_velocity if insight else None,
        novelty_score=insight.novelty_score if insight else None,
        coverage_score=insight.coverage_score if insight else None,
        recommendation=insight.recommendation.value if insight and insight.recommendation else None,
        summary=insight.summary if insight else None,
        insight_calculated_at=insight.calculated_at if insight else None,
        members=members,
    )
