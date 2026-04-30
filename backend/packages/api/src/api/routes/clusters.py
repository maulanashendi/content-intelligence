import uuid
from datetime import UTC, datetime, timedelta

from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterInsight,
    ContentSource,
    InsightRecommendation,
    SourceType,
)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import SessionDep

router = APIRouter(prefix="/clusters", tags=["clusters"])


class ClusterSummary(BaseModel):
    id: uuid.UUID
    label: str | None
    member_count: int | None
    trend_velocity: float | None
    novelty_score: float | None
    coverage_score: float | None
    recommendation: str | None


class ArticleSummary(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    first_paragraph: str | None
    published_at: datetime | None
    source_name: str
    relevance_score: float | None


class ClusterDetail(ClusterSummary):
    members: list[ArticleSummary]


def _to_summary(cluster: ArticleCluster, insight: ClusterInsight) -> ClusterSummary:
    return ClusterSummary(
        id=cluster.id,
        label=cluster.label,
        member_count=cluster.member_count,
        trend_velocity=insight.trend_velocity,
        novelty_score=insight.novelty_score,
        coverage_score=insight.coverage_score,
        recommendation=insight.recommendation.value if insight.recommendation else None,
    )


@router.get("/morning", response_model=list[ClusterSummary])
async def morning_clusters(session: SessionDep) -> list[ClusterSummary]:
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

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
        select(ArticleCluster, ClusterInsight)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
        .where(
            ArticleCluster.is_current.is_(True),
            ClusterInsight.recommendation.in_(
                [
                    InsightRecommendation.trending,
                    InsightRecommendation.worth_writing,
                ]
            ),
            ~has_internal_recent,
        )
        .order_by(ClusterInsight.trend_velocity.desc().nullslast())
        .limit(10)
    )

    rows = (await session.execute(stmt)).all()
    return [_to_summary(cluster, insight) for cluster, insight in rows]


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


@router.get("/{cluster_id}", response_model=ClusterDetail)
async def cluster_detail(cluster_id: uuid.UUID, session: SessionDep) -> ClusterDetail:
    cluster_stmt = (
        select(ArticleCluster, ClusterInsight)
        .join(ClusterInsight, ClusterInsight.cluster_id == ArticleCluster.id)
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
        trend_velocity=insight.trend_velocity,
        novelty_score=insight.novelty_score,
        coverage_score=insight.coverage_score,
        recommendation=insight.recommendation.value if insight.recommendation else None,
        members=members,
    )
