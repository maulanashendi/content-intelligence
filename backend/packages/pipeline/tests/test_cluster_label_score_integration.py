"""Integration test for pipeline.cluster_label_score.run().

Seeds articles + pre-computed fake embeddings directly into the DB (bypassing
the embedding pipeline), then runs cluster→label→score and asserts:
  - article_cluster rows exist with non-null labels
  - cluster_insight rows exist for each leaf cluster

This is the regression test for the "cluster map shows IDs" bug: if labeling
never runs or silently skips all clusters, this test fails.
"""

import uuid
from datetime import UTC, datetime

import pytest
from core.config import settings
from core.db import get_session
from core.models import (
    Article,
    ArticleCluster,
    ArticleEmbedding,
    ClusterInsight,
    ContentSource,
    SourceType,
)
from sqlalchemy import select

from pipeline.cluster_label_score import run

_NOW = datetime.now(UTC).replace(tzinfo=None)
ARTICLES_PER_CLUSTER = 6
NUM_CLUSTERS = 3


async def _seed_articles_with_embeddings(
    session,
    source_id: uuid.UUID,
    fake_embedder,
) -> list[Article]:
    articles = []
    for cluster_idx in range(NUM_CLUSTERS):
        for member_idx in range(ARTICLES_PER_CLUSTER):
            title = f"{cluster_idx}|article {cluster_idx}-{member_idx}"
            article = Article(
                id=uuid.uuid4(),
                source_id=source_id,
                title=title,
                url=f"https://fake.example.com/{cluster_idx}/{member_idx}/{uuid.uuid4()}",
                published_at=_NOW,
            )
            articles.append(article)
            session.add(article)

    await session.flush()

    for article in articles:
        vector = fake_embedder.encode([article.title])[0].tolist()
        session.add(
            ArticleEmbedding(
                id=uuid.uuid4(),
                article_id=article.id,
                model_name="fake",
                embedding=vector,
            )
        )

    return articles


@pytest.mark.asyncio
async def test_run_writes_labels_and_insights_end_to_end(
    clean_db, fake_embedder, monkeypatch
):
    monkeypatch.setattr(settings, "umap_target_dimensions", 5)

    source = ContentSource(
        id=uuid.uuid4(),
        name="Fake RSS",
        url="https://fake.example.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
    )

    async with get_session() as session:
        session.add(source)
        await session.flush()
        await _seed_articles_with_embeddings(session, source.id, fake_embedder)
        await session.commit()

    label_counter = {"n": 0}

    async def fake_label(_reps):
        label_counter["n"] += 1
        n = label_counter["n"]
        return {
            "label": f"Topic {n}",
            "what_happened": f"Apa terjadi {n}",
            "parties_involved": [f"Pihak {n}A", f"Pihak {n}B"],
            "editorial_angle": f"Sudut {n}",
            "summary": [f"Klaim {n}"],
        }

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", fake_label)

    await run()

    async with get_session() as session:
        clusters = list(
            (
                await session.execute(
                    select(ArticleCluster).where(ArticleCluster.is_current.is_(True))
                )
            )
            .scalars()
            .all()
        )
        insight_rows = list((await session.execute(select(ClusterInsight))).scalars().all())

    assert clusters, "clustering must produce at least one cluster"

    labeled = [c for c in clusters if c.label is not None]
    assert labeled, (
        "At least one cluster must have a non-null label — "
        "this failure means labeling never ran or skipped all clusters"
    )

    assert insight_rows, "scoring must upsert cluster_insight rows"
    assert all(
        isinstance(row.competitor_count, int)
        and isinstance(row.tempo_covered, bool)
        and isinstance(row.underperformed, bool)
        for row in insight_rows
    ), "cluster_insight rows must have all required raw-signal fields"


@pytest.mark.asyncio
async def test_run_idempotent(clean_db, fake_embedder, monkeypatch):
    monkeypatch.setattr(settings, "umap_target_dimensions", 5)

    source = ContentSource(
        id=uuid.uuid4(),
        name="Fake RSS",
        url="https://fake.example.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
    )

    async with get_session() as session:
        session.add(source)
        await session.flush()
        await _seed_articles_with_embeddings(session, source.id, fake_embedder)
        await session.commit()

    counter = {"n": 0}

    async def fake_label(_reps):
        counter["n"] += 1
        n = counter["n"]
        return {
            "label": f"Topic {n}",
            "what_happened": f"Apa terjadi {n}",
            "parties_involved": [f"Pihak {n}A", f"Pihak {n}B"],
            "editorial_angle": f"Sudut {n}",
            "summary": [f"Klaim {n}"],
        }

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", fake_label)

    await run()

    async with get_session() as session:
        first_current = list(
            (
                await session.execute(
                    select(ArticleCluster).where(ArticleCluster.is_current.is_(True))
                )
            )
            .scalars()
            .all()
        )
        first_current_ids = {c.id for c in first_current}
        first_insight_count = len(
            (
                await session.execute(
                    select(ClusterInsight).where(
                        ClusterInsight.cluster_id.in_(first_current_ids)
                    )
                )
            )
            .scalars()
            .all()
        )

    await run()

    async with get_session() as session:
        second_current = list(
            (
                await session.execute(
                    select(ArticleCluster).where(ArticleCluster.is_current.is_(True))
                )
            )
            .scalars()
            .all()
        )
        second_current_ids = {c.id for c in second_current}
        second_insight_count = len(
            (
                await session.execute(
                    select(ClusterInsight).where(
                        ClusterInsight.cluster_id.in_(second_current_ids)
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(first_current) == len(second_current), (
        "Second run must produce the same number of current clusters from the same data"
    )
    assert first_insight_count == second_insight_count, (
        "Each current cluster must have exactly one insight row (upsert, not append)"
    )
