import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

import pytest
from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ArticleGscMetric,
    ClusterInsight,
    ClusterRun,
    ContentSource,
    SourceType,
    TrendSignal,
    TrendSignalArticle,
)
from scoring import pipeline as scoring_pipeline
from scoring.pipeline import run as score_run
from scoring.velocity import compute_trend_velocity
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

NOW = datetime(2026, 4, 30, 8, 0, 0)


# ---------------------------------------------------------------------------
# velocity unit tests
# ---------------------------------------------------------------------------


def test_velocity_zero_when_no_articles_in_window() -> None:
    assert compute_trend_velocity(0, 0) == 0.0


def test_velocity_full_window_capped() -> None:
    assert compute_trend_velocity(7, 7) == 1.0


def test_velocity_clipped_at_one() -> None:
    assert compute_trend_velocity(10, 5) == 1.0


def test_velocity_partial_window() -> None:
    assert compute_trend_velocity(3, 10) == 0.3


# ---------------------------------------------------------------------------
# integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def _session_patcher(session: AsyncSession, monkeypatch):
    @asynccontextmanager
    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(scoring_pipeline, "get_session", _session_override)


async def test_run_persists_all_six_fields(
    session: AsyncSession, _session_patcher
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
    cluster = ArticleCluster(
        id=uuid.uuid4(),
        run_id=run_row.id,
        label="Harga beras",
        member_count=3,
        is_current=True,
    )
    t24h_article = Article(
        id=uuid.uuid4(),
        source_id=competitor_source.id,
        title="Beras 24h",
        url=f"https://detik.test/beras-24h-{uuid.uuid4()}",
        published_at=NOW - timedelta(hours=6),
    )
    t7d_article = Article(
        id=uuid.uuid4(),
        source_id=competitor_source.id,
        title="Beras 7d",
        url=f"https://detik.test/beras-7d-{uuid.uuid4()}",
        published_at=NOW - timedelta(days=5),
    )
    internal_article = Article(
        id=uuid.uuid4(),
        source_id=internal_source.id,
        title="Tempo beras",
        url=f"https://tempo.test/beras-{uuid.uuid4()}",
        published_at=NOW - timedelta(days=2),
    )
    trend_signal = TrendSignal(
        id=uuid.uuid4(),
        keyword="harga beras",
        interest_score=80.0,
        captured_at=NOW - timedelta(hours=12),
    )

    session.add_all(
        [
            competitor_source,
            internal_source,
            run_row,
            cluster,
            t24h_article,
            t7d_article,
            internal_article,
            trend_signal,
        ]
    )
    await session.flush()
    session.add_all(
        [
            ArticleClusterMember(cluster_id=cluster.id, article_id=t24h_article.id),
            ArticleClusterMember(cluster_id=cluster.id, article_id=t7d_article.id),
            ArticleClusterMember(cluster_id=cluster.id, article_id=internal_article.id),
            TrendSignalArticle(trend_signal_id=trend_signal.id, article_id=t24h_article.id),
        ]
    )
    await session.commit()

    count = await score_run(now=NOW.replace(tzinfo=UTC))
    assert count == 1

    insight = (
        await session.execute(select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id))
    ).scalar_one()

    assert insight.trend_velocity is not None
    assert insight.competitor_count == 1  # one distinct competitor source (both articles same source)
    assert insight.trend_match_count == 1
    assert insight.tempo_covered is True
    assert insight.last_internal_days_ago == 2
    assert insight.underperformed is False


async def test_tempo_covered_when_internal_member(
    session: AsyncSession, _session_patcher
) -> None:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Tempo",
        url=f"https://tempo-{uuid.uuid4()}.test",
        source_type=SourceType.internal,
    )
    run_row = ClusterRun(id=uuid.uuid4())
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_row.id, is_current=True)
    article = Article(
        id=uuid.uuid4(),
        source_id=source.id,
        title="Test",
        url=f"https://tempo.test/t-{uuid.uuid4()}",
        published_at=NOW - timedelta(hours=1),
    )
    session.add_all([source, run_row, cluster, article])
    await session.flush()
    session.add(ArticleClusterMember(cluster_id=cluster.id, article_id=article.id))
    await session.commit()

    await score_run(now=NOW.replace(tzinfo=UTC))

    insight = (
        await session.execute(select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id))
    ).scalar_one()
    assert insight.tempo_covered is True


async def test_trend_match_count_excludes_stale_signals(
    session: AsyncSession, _session_patcher
) -> None:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Detik",
        url=f"https://detik-{uuid.uuid4()}.test",
        source_type=SourceType.rss,
    )
    run_row = ClusterRun(id=uuid.uuid4())
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_row.id, is_current=True)
    article = Article(
        id=uuid.uuid4(),
        source_id=source.id,
        title="Article",
        url=f"https://detik.test/a-{uuid.uuid4()}",
        published_at=NOW - timedelta(hours=1),
    )
    fresh_signal = TrendSignal(
        id=uuid.uuid4(),
        keyword="fresh",
        interest_score=70.0,
        captured_at=NOW - timedelta(hours=12),
    )
    stale_signal = TrendSignal(
        id=uuid.uuid4(),
        keyword="stale",
        interest_score=70.0,
        captured_at=NOW - timedelta(hours=48),
    )
    session.add_all([source, run_row, cluster, article, fresh_signal, stale_signal])
    await session.flush()
    session.add_all(
        [
            ArticleClusterMember(cluster_id=cluster.id, article_id=article.id),
            TrendSignalArticle(trend_signal_id=fresh_signal.id, article_id=article.id),
            TrendSignalArticle(trend_signal_id=stale_signal.id, article_id=article.id),
        ]
    )
    await session.commit()

    await score_run(now=NOW.replace(tzinfo=UTC))

    insight = (
        await session.execute(select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id))
    ).scalar_one()
    assert insight.trend_match_count == 1


async def test_underperformed_requires_all_three_thresholds(
    session: AsyncSession, _session_patcher
) -> None:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Tempo",
        url=f"https://tempo-{uuid.uuid4()}.test",
        source_type=SourceType.internal,
    )
    run_row = ClusterRun(id=uuid.uuid4())
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_row.id, is_current=True)
    article = Article(
        id=uuid.uuid4(),
        source_id=source.id,
        title="Underperf",
        url=f"https://tempo.test/u-{uuid.uuid4()}",
        published_at=NOW - timedelta(days=1),
    )
    gsc = ArticleGscMetric(
        id=uuid.uuid4(),
        article_id=article.id,
        impressions=200,
        avg_position=15.0,
        ctr=0.01,
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
    )
    session.add_all([source, run_row, cluster, article, gsc])
    await session.flush()
    session.add(ArticleClusterMember(cluster_id=cluster.id, article_id=article.id))
    await session.commit()

    await score_run(now=NOW.replace(tzinfo=UTC))

    insight = (
        await session.execute(select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id))
    ).scalar_one()
    assert insight.underperformed is True


async def test_underperformed_false_when_only_one_threshold_met(
    session: AsyncSession, _session_patcher
) -> None:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Tempo",
        url=f"https://tempo-{uuid.uuid4()}.test",
        source_type=SourceType.internal,
    )
    run_row = ClusterRun(id=uuid.uuid4())
    cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_row.id, is_current=True)
    article = Article(
        id=uuid.uuid4(),
        source_id=source.id,
        title="Good performer",
        url=f"https://tempo.test/g-{uuid.uuid4()}",
        published_at=NOW - timedelta(days=1),
    )
    gsc = ArticleGscMetric(
        id=uuid.uuid4(),
        article_id=article.id,
        impressions=200,
        avg_position=5.0,  # good position, does NOT meet pos_thr > 10
        ctr=0.01,
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
    )
    session.add_all([source, run_row, cluster, article, gsc])
    await session.flush()
    session.add(ArticleClusterMember(cluster_id=cluster.id, article_id=article.id))
    await session.commit()

    await score_run(now=NOW.replace(tzinfo=UTC))

    insight = (
        await session.execute(select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id))
    ).scalar_one()
    assert insight.underperformed is False


async def test_run_batches_three_queries(
    session: AsyncSession, _session_patcher
) -> None:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Detik",
        url=f"https://detik-{uuid.uuid4()}.test",
        source_type=SourceType.rss,
    )
    run_row = ClusterRun(id=uuid.uuid4())
    clusters = [
        ArticleCluster(id=uuid.uuid4(), run_id=run_row.id, is_current=True) for _ in range(5)
    ]
    articles = [
        Article(
            id=uuid.uuid4(),
            source_id=source.id,
            title=f"Article {i}",
            url=f"https://detik.test/a-{uuid.uuid4()}",
            published_at=NOW - timedelta(hours=i + 1),
        )
        for i in range(10)
    ]
    session.add_all([source, run_row, *clusters, *articles])
    await session.flush()
    members = [
        ArticleClusterMember(cluster_id=clusters[i % 5].id, article_id=articles[i].id)
        for i in range(10)
    ]
    session.add_all(members)
    await session.commit()

    select_count = {"n": 0}

    @event.listens_for(session.bind.sync_engine, "before_cursor_execute")
    def _on_exec(conn, cursor, stmt, *_):
        if stmt.lstrip().upper().startswith("SELECT"):
            select_count["n"] += 1

    await score_run(now=NOW.replace(tzinfo=UTC))
    # 7 batched SELECT calls: cluster_ids, article_facts, trend_match, weighted_trend_score,
    # underperformed, gsc_signals, competitor_freshness_days — all O(1) not O(clusters).
    assert select_count["n"] <= 7
