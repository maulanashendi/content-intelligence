import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ArticleGscMetric,
    ClusterInsight,
    ClusterRun,
    ContentSource,
    InsightRecommendation,
    SourceType,
    TrendSignal,
    TrendSignalArticle,
)
from scoring import pipeline as scoring_pipeline
from scoring.coverage import CoverageInputs, compute_coverage_score
from scoring.novelty import compute_novelty_score
from scoring.pipeline import _load_cluster_facts, run
from scoring.velocity import compute_trend_velocity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

NOW = datetime(2026, 4, 30, 8, 0, 0)


def test_compute_trend_velocity_prefers_recent_and_trending_articles() -> None:
    score = compute_trend_velocity(
        [
            NOW - timedelta(hours=6),
            NOW - timedelta(days=1),
            NOW - timedelta(days=2),
        ],
        [90.0, 80.0],
        now=NOW,
    )

    assert score > 0.75


def test_compute_novelty_score_drops_for_older_topics() -> None:
    fresh_score = compute_novelty_score([NOW - timedelta(days=2)], now=NOW)
    stale_score = compute_novelty_score([NOW - timedelta(days=40)], now=NOW)

    assert fresh_score > stale_score
    assert stale_score == 0.0


def test_compute_coverage_score_rewards_competitor_gap() -> None:
    no_internal = compute_coverage_score(
        CoverageInputs(
            competitor_articles=4,
            internal_articles=0,
            recent_internal_articles=0,
            internal_underperformed=False,
        )
    )
    recent_internal = compute_coverage_score(
        CoverageInputs(
            competitor_articles=4,
            internal_articles=1,
            recent_internal_articles=1,
            internal_underperformed=False,
        )
    )

    assert no_internal > recent_internal


async def test_load_cluster_facts_deduplicates_articles_but_keeps_all_interest_scores(
    session: AsyncSession,
) -> None:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Detik",
        url=f"https://detik-{uuid.uuid4()}.test",
        source_type=SourceType.rss,
    )
    run_row = ClusterRun(id=uuid.uuid4())
    cluster = ArticleCluster(
        id=uuid.uuid4(),
        run_id=run_row.id,
        label="Rice prices",
        member_count=1,
        is_current=True,
    )
    article = Article(
        id=uuid.uuid4(),
        source_id=source.id,
        title="Harga beras naik",
        url=f"https://detik.test/rice-{uuid.uuid4()}",
        published_at=NOW - timedelta(hours=4),
    )
    signals = [
        TrendSignal(
            id=uuid.uuid4(),
            keyword="Harga beras",
            interest_score=92.0,
            captured_at=NOW - timedelta(hours=1),
        ),
        TrendSignal(
            id=uuid.uuid4(),
            keyword="Harga pangan",
            interest_score=88.0,
            captured_at=NOW - timedelta(hours=2),
        ),
    ]

    session.add_all([source, run_row, cluster, article, *signals])
    await session.flush()
    session.add_all(
        [
            ArticleClusterMember(cluster_id=cluster.id, article_id=article.id),
            *(TrendSignalArticle(trend_signal_id=signal.id, article_id=article.id) for signal in signals),
        ]
    )
    await session.flush()

    facts = await _load_cluster_facts(session, cluster.id, NOW)

    assert facts.competitor_articles == 1
    assert facts.internal_articles == 0
    assert facts.recent_internal_articles == 0
    assert facts.published_at_values == [article.published_at]
    assert sorted(facts.interest_scores) == [88.0, 92.0]


async def test_run_persists_cluster_insights_with_recommendations(
    session: AsyncSession,
    monkeypatch,
) -> None:
    competitor_source = ContentSource(
        id=uuid.uuid4(),
        name="Detik",
        url=f"https://detik-{uuid.uuid4()}.test",
        source_type=SourceType.rss,
    )
    internal_source = ContentSource(
        id=uuid.uuid4(),
        name="Tempo",
        url=f"https://tempo-{uuid.uuid4()}.test",
        source_type=SourceType.internal,
    )
    run_row = ClusterRun(id=uuid.uuid4())

    trending_cluster = ArticleCluster(
        id=uuid.uuid4(),
        run_id=run_row.id,
        label="Rice prices",
        member_count=3,
        is_current=True,
    )
    saturated_cluster = ArticleCluster(
        id=uuid.uuid4(),
        run_id=run_row.id,
        label="BI rate",
        member_count=2,
        is_current=True,
    )

    trending_articles = [
        Article(
            id=uuid.uuid4(),
            source_id=competitor_source.id,
            title=f"Trending {index}",
            url=f"https://detik.test/trending-{index}-{uuid.uuid4()}",
            published_at=NOW - timedelta(hours=index + 2),
        )
        for index in range(3)
    ]
    saturated_articles = [
        Article(
            id=uuid.uuid4(),
            source_id=competitor_source.id if index == 0 else internal_source.id,
            title=f"Saturated {index}",
            url=f"https://tempo.test/saturated-{index}-{uuid.uuid4()}",
            published_at=NOW - timedelta(days=1 if index == 0 else 2),
        )
        for index in range(2)
    ]

    trend_signal = TrendSignal(
        id=uuid.uuid4(),
        keyword="Harga beras",
        interest_score=92.0,
        captured_at=NOW - timedelta(hours=1),
    )

    session.add_all(
        [
            competitor_source,
            internal_source,
            run_row,
            trending_cluster,
            saturated_cluster,
            *trending_articles,
            *saturated_articles,
            trend_signal,
        ]
    )
    await session.flush()

    session.add_all(
        [
            *(ArticleClusterMember(cluster_id=trending_cluster.id, article_id=article.id) for article in trending_articles),
            *(ArticleClusterMember(cluster_id=saturated_cluster.id, article_id=article.id) for article in saturated_articles),
            *(TrendSignalArticle(trend_signal_id=trend_signal.id, article_id=article.id) for article in trending_articles),
            ArticleGscMetric(
                id=uuid.uuid4(),
                article_id=saturated_articles[1].id,
                ctr=0.01,
                avg_position=24.0,
                period_start=date(2026, 4, 1),
                period_end=date(2026, 4, 30),
            ),
        ]
    )
    await session.commit()

    @asynccontextmanager
    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(scoring_pipeline, "get_session", _session_override)

    scored_count = await run(now=NOW.replace(tzinfo=UTC))

    assert scored_count >= 2

    insight_rows = (
        await session.execute(
            select(ClusterInsight).where(
                ClusterInsight.cluster_id.in_([trending_cluster.id, saturated_cluster.id])
            )
        )
    ).scalars().all()
    by_cluster = {row.cluster_id: row for row in insight_rows}

    assert by_cluster[trending_cluster.id].recommendation == InsightRecommendation.trending
    assert by_cluster[saturated_cluster.id].recommendation == InsightRecommendation.saturated
    assert by_cluster[trending_cluster.id].trend_velocity is not None
    assert by_cluster[trending_cluster.id].novelty_score is not None
    assert by_cluster[trending_cluster.id].coverage_score is not None
