from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from core.db import get_session
from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ArticleGscMetric,
    ClusterInsight,
    ContentSource,
    InsightRecommendation,
    SourceType,
    TrendSignal,
    TrendSignalArticle,
)
from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from scoring.coverage import CoverageInputs, compute_coverage_score
from scoring.novelty import compute_novelty_score
from scoring.velocity import compute_trend_velocity

RECENT_INTERNAL_WINDOW_DAYS = 30


@dataclass(slots=True)
class ClusterArticleFacts:
    published_at_values: list[datetime | None]
    interest_scores: list[float]
    competitor_articles: int
    internal_articles: int
    recent_internal_articles: int
    internal_underperformed: bool


async def run(*, now: datetime | None = None) -> int:
    current_time = _normalize_now(now)
    async with get_session() as session:
        cluster_ids = await _current_cluster_ids(session)
        for cluster_id in cluster_ids:
            facts = await _load_cluster_facts(session, cluster_id, current_time)
            await _upsert_cluster_insight(session, cluster_id, facts, current_time)
        await session.commit()
    return len(cluster_ids)


async def _current_cluster_ids(session: AsyncSession) -> Sequence[UUID]:
    stmt = select(ArticleCluster.id).where(ArticleCluster.is_current.is_(True))
    return list((await session.execute(stmt)).scalars())


async def _load_cluster_facts(
    session: AsyncSession,
    cluster_id: UUID,
    now: datetime,
) -> ClusterArticleFacts:
    recent_internal_cutoff = now - timedelta(days=RECENT_INTERNAL_WINDOW_DAYS)

    article_rows = (await session.execute(_cluster_article_stmt(cluster_id))).all()
    interest_scores = await _cluster_interest_scores(session, cluster_id)

    published_at_values = [row.published_at for row in article_rows]

    competitor_articles = sum(1 for row in article_rows if row.source_type == SourceType.rss)
    internal_articles = sum(1 for row in article_rows if row.source_type == SourceType.internal)
    recent_internal_articles = sum(
        1
        for row in article_rows
        if row.source_type == SourceType.internal
        and row.published_at is not None
        and _normalize_now(row.published_at) >= recent_internal_cutoff
    )

    internal_article_ids = [
        row.article_id for row in article_rows if row.source_type == SourceType.internal
    ]
    internal_underperformed = False
    if internal_article_ids:
        internal_underperformed = await _has_underperformed_internal_articles(
            session, internal_article_ids
        )

    return ClusterArticleFacts(
        published_at_values=published_at_values,
        interest_scores=interest_scores,
        competitor_articles=competitor_articles,
        internal_articles=internal_articles,
        recent_internal_articles=recent_internal_articles,
        internal_underperformed=internal_underperformed,
    )


def _cluster_article_stmt(cluster_id: UUID) -> Select[tuple[Any, ...]]:
    return (
        select(
            Article.id.label("article_id"),
            Article.published_at,
            ContentSource.source_type,
        )
        .select_from(ArticleClusterMember)
        .join(Article, Article.id == ArticleClusterMember.article_id)
        .join(ContentSource, ContentSource.id == Article.source_id)
        .where(ArticleClusterMember.cluster_id == cluster_id)
    )


async def _cluster_interest_scores(session: AsyncSession, cluster_id: UUID) -> list[float]:
    stmt = (
        select(TrendSignal.interest_score)
        .select_from(ArticleClusterMember)
        .join(Article, Article.id == ArticleClusterMember.article_id)
        .join(TrendSignalArticle, TrendSignalArticle.article_id == Article.id)
        .join(TrendSignal, TrendSignal.id == TrendSignalArticle.trend_signal_id)
        .where(ArticleClusterMember.cluster_id == cluster_id)
        .where(TrendSignal.interest_score.is_not(None))
    )
    return list((await session.execute(stmt)).scalars())


async def _has_underperformed_internal_articles(
    session: AsyncSession,
    article_ids: Sequence[UUID],
) -> bool:
    stmt = select(ArticleGscMetric.ctr, ArticleGscMetric.avg_position).where(
        ArticleGscMetric.article_id.in_(article_ids)
    )
    rows = (await session.execute(stmt)).all()
    return any(
        (row.ctr is not None and row.ctr < 0.02)
        or (row.avg_position is not None and row.avg_position > 20)
        for row in rows
    )


async def _upsert_cluster_insight(
    session: AsyncSession,
    cluster_id: UUID,
    facts: ClusterArticleFacts,
    now: datetime,
) -> None:
    trend_velocity = compute_trend_velocity(
        facts.published_at_values,
        facts.interest_scores,
        now=now,
    )
    novelty_score = compute_novelty_score(facts.published_at_values, now=now)
    coverage_score = compute_coverage_score(
        CoverageInputs(
            competitor_articles=facts.competitor_articles,
            internal_articles=facts.internal_articles,
            recent_internal_articles=facts.recent_internal_articles,
            internal_underperformed=facts.internal_underperformed,
        )
    )

    stmt = pg_insert(ClusterInsight).values(
        cluster_id=cluster_id,
        trend_velocity=trend_velocity,
        novelty_score=novelty_score,
        coverage_score=coverage_score,
        recommendation=_derive_recommendation(
            trend_velocity=trend_velocity,
            novelty_score=novelty_score,
            coverage_score=coverage_score,
            recent_internal_articles=facts.recent_internal_articles,
        ),
        calculated_at=now,
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["cluster_id"],
            set_={
                "trend_velocity": stmt.excluded.trend_velocity,
                "novelty_score": stmt.excluded.novelty_score,
                "coverage_score": stmt.excluded.coverage_score,
                "recommendation": stmt.excluded.recommendation,
                "calculated_at": stmt.excluded.calculated_at,
            },
        )
    )


def _derive_recommendation(
    *,
    trend_velocity: float,
    novelty_score: float,
    coverage_score: float,
    recent_internal_articles: int,
) -> InsightRecommendation:
    if recent_internal_articles > 0 and coverage_score < 0.55:
        return InsightRecommendation.saturated
    if trend_velocity >= 0.65 and novelty_score >= 0.45:
        return InsightRecommendation.trending
    if coverage_score >= 0.4:
        return InsightRecommendation.worth_writing
    return InsightRecommendation.saturated


def _normalize_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(tzinfo=None)
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value
