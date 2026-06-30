"""Integration tests for labeling.pipeline.run() against a real Postgres database.

These replace the mocked tests in test_label_pipeline.py, which patched
session.execute() and could not detect broken SQL queries.
"""

import uuid
from datetime import UTC, datetime

import pytest
from core.db import get_session
from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterInsight,
    ClusterRun,
    ContentSource,
    SourceType,
)
from sqlalchemy import select

from labeling.pipeline import _upsert_insight, run

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _source() -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        name="Test",
        url=f"https://test-{uuid.uuid4()}.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
    )


def _article(source_id: uuid.UUID, title: str) -> Article:
    return Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title=title,
        url=f"https://test-{uuid.uuid4()}.com/a",
        published_at=_NOW,
    )


def _fake_factory(prefix: str = "label") -> tuple[list[str], "callable"]:
    log: list[str] = []

    async def fake(reps):
        cid = str(uuid.uuid4())[:8]
        log.append(cid)
        return {
            "label": f"{prefix}-{cid}",
            "what_happened": f"Apa terjadi {cid}",
            "parties_involved": [f"Pihak A {cid}", f"Pihak B {cid}"],
            "editorial_angle": f"Sudut {cid}",
            "summary": [f"Klaim {cid}"],
        }

    return log, fake


@pytest.mark.asyncio
async def test_run_writes_labels_and_insight_to_leaf_clusters(clean_db, monkeypatch):
    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())

    async with get_session() as session:
        session.add_all([source, run_row])
        await session.flush()

        cluster1 = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=3
        )
        cluster2 = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=3
        )
        session.add_all([cluster1, cluster2])
        await session.flush()

        for idx, cluster in enumerate([cluster1, cluster2]):
            for j in range(3):
                article = _article(source.id, f"Artikel {idx}-{j}")
                session.add(article)
                await session.flush()
                session.add(
                    ArticleClusterMember(
                        cluster_id=cluster.id, article_id=article.id, relevance_score=1.0
                    )
                )

        await session.commit()

    _, fake = _fake_factory()
    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", fake)

    result = await run()

    assert result["labeled"] == 2
    assert result["skipped"] == 0

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
        insights = list((await session.execute(select(ClusterInsight))).scalars().all())

    assert all(c.label is not None for c in clusters)
    assert len({c.label for c in clusters}) == 2

    assert len(insights) == 2, "One ClusterInsight row per leaf cluster"
    assert all(i.what_happened for i in insights)
    assert all(i.parties_involved and len(i.parties_involved) == 2 for i in insights)
    assert all(i.editorial_angle for i in insights)


@pytest.mark.asyncio
async def test_run_skips_parent_clusters(clean_db, monkeypatch):
    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())

    async with get_session() as session:
        session.add_all([source, run_row])
        await session.flush()

        parent = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=6
        )
        session.add(parent)
        await session.flush()

        child1 = ArticleCluster(
            id=uuid.uuid4(),
            run_id=run_row.id,
            parent_cluster_id=parent.id,
            is_current=True,
            member_count=3,
        )
        child2 = ArticleCluster(
            id=uuid.uuid4(),
            run_id=run_row.id,
            parent_cluster_id=parent.id,
            is_current=True,
            member_count=3,
        )
        session.add_all([child1, child2])
        await session.flush()

        for idx, cluster in enumerate([child1, child2]):
            for j in range(3):
                article = _article(source.id, f"Artikel {idx}-{j}")
                session.add(article)
                await session.flush()
                session.add(
                    ArticleClusterMember(
                        cluster_id=cluster.id, article_id=article.id, relevance_score=1.0
                    )
                )

        await session.commit()

    _, fake = _fake_factory("child")
    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", fake)

    result = await run()

    assert result["labeled"] == 2

    async with get_session() as session:
        parent_row = await session.get(ArticleCluster, parent.id)
        child1_row = await session.get(ArticleCluster, child1.id)
        child2_row = await session.get(ArticleCluster, child2.id)
        parent_insight = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == parent.id)
            )
        ).scalar_one_or_none()

    assert parent_row.label is None, "Parent cluster must not be labeled"
    assert child1_row.label is not None
    assert child2_row.label is not None
    assert parent_insight is None, "Parent must not get an insight row"


@pytest.mark.asyncio
async def test_run_skips_cluster_with_no_articles(clean_db):
    run_row = ClusterRun(id=uuid.uuid4())

    async with get_session() as session:
        session.add(run_row)
        await session.flush()
        cluster = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=0
        )
        session.add(cluster)
        await session.commit()

    result = await run()

    assert result["labeled"] == 0
    assert result["skipped"] == 1

    async with get_session() as session:
        row = await session.get(ArticleCluster, cluster.id)

    assert row.label is None


@pytest.mark.asyncio
async def test_run_skips_cluster_on_llm_error(clean_db, monkeypatch):
    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())

    async with get_session() as session:
        session.add_all([source, run_row])
        await session.flush()

        cluster = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=2
        )
        session.add(cluster)
        await session.flush()

        for j in range(2):
            article = _article(source.id, f"Artikel error {j}")
            session.add(article)
            await session.flush()
            session.add(
                ArticleClusterMember(
                    cluster_id=cluster.id, article_id=article.id, relevance_score=1.0
                )
            )

        await session.commit()

    async def boom(_):
        raise RuntimeError("OOM")

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", boom)
    monkeypatch.setattr("labeling.pipeline.generate_label", boom)

    result = await run()

    assert result["labeled"] == 0
    assert result["skipped"] == 1

    async with get_session() as session:
        row = await session.get(ArticleCluster, cluster.id)
        insight = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

    assert row.label is None, "Label must remain NULL after LLM error"
    assert insight is None, "No insight should be written when LLM fails"


@pytest.mark.asyncio
async def test_run_skips_cluster_when_llm_returns_no_label(clean_db, monkeypatch):
    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())

    async with get_session() as session:
        session.add_all([source, run_row])
        await session.flush()

        cluster = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=2
        )
        session.add(cluster)
        await session.flush()
        for j in range(2):
            article = _article(source.id, f"Artikel kosong {j}")
            session.add(article)
            await session.flush()
            session.add(
                ArticleClusterMember(
                    cluster_id=cluster.id, article_id=article.id, relevance_score=1.0
                )
            )
        await session.commit()

    async def empty(_):
        return {
            "label": None,
            "what_happened": "ada",
            "parties_involved": ["A"],
            "editorial_angle": "ada",
            "summary": None,
        }

    async def boom_fallback(_):
        raise RuntimeError("fallback also failed")

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", empty)
    monkeypatch.setattr("labeling.pipeline.generate_label", boom_fallback)

    result = await run()

    assert result["labeled"] == 0
    assert result["skipped"] == 1

    async with get_session() as session:
        row = await session.get(ArticleCluster, cluster.id)
        insight = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

    assert row.label is None
    assert insight is None, "No insight written if label missing"


async def _make_cluster_with_articles(session_factory, source, run_row, title_prefix="Artikel"):
    """Helper: create a leaf cluster with 2 articles and return the cluster."""
    async with session_factory() as session:
        cluster = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=2
        )
        session.add(cluster)
        await session.flush()
        for j in range(2):
            article = _article(source.id, f"{title_prefix} {j}")
            session.add(article)
            await session.flush()
            session.add(
                ArticleClusterMember(
                    cluster_id=cluster.id, article_id=article.id, relevance_score=1.0
                )
            )
        await session.commit()
    return cluster


@pytest.mark.asyncio
async def test_run_uses_fallback_label_when_insight_raises(clean_db, monkeypatch):
    from core.db import get_session

    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())
    async with get_session() as session:
        session.add_all([source, run_row])
        await session.commit()

    cluster = await _make_cluster_with_articles(get_session, source, run_row, "Fallback Insight Raises")

    async def boom_insight(_):
        raise RuntimeError("OOM in insight")

    async def good_label(_):
        return "Label Dari Fallback"

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", boom_insight)
    monkeypatch.setattr("labeling.pipeline.generate_label", good_label)

    result = await run()

    assert result["labeled"] == 1
    assert result["skipped"] == 0

    async with get_session() as session:
        row = await session.get(ArticleCluster, cluster.id)
        insight = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

    assert row.label == "Label Dari Fallback"
    assert insight is not None, "ClusterInsight row must be written even with fallback label"
    assert insight.what_happened is None
    assert insight.parties_involved is None
    assert insight.editorial_angle is None


@pytest.mark.asyncio
async def test_run_uses_fallback_label_when_insight_returns_no_label(clean_db, monkeypatch):
    from core.db import get_session

    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())
    async with get_session() as session:
        session.add_all([source, run_row])
        await session.commit()

    cluster = await _make_cluster_with_articles(get_session, source, run_row, "Fallback No Label")

    async def no_label(_):
        return {
            "label": None,
            "what_happened": "ada",
            "parties_involved": ["A"],
            "editorial_angle": "ada",
            "summary": None,
        }

    async def good_label(_):
        return "Label Dari Fallback"

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", no_label)
    monkeypatch.setattr("labeling.pipeline.generate_label", good_label)

    result = await run()

    assert result["labeled"] == 1
    assert result["skipped"] == 0

    async with get_session() as session:
        row = await session.get(ArticleCluster, cluster.id)
        insight = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

    assert row.label == "Label Dari Fallback"
    assert insight is not None, "ClusterInsight row must be written even with fallback label"
    # Partial insight from a no-label response is not written (reset to None)
    assert insight.what_happened is None
    assert insight.parties_involved is None
    assert insight.editorial_angle is None


@pytest.mark.asyncio
async def test_run_skips_cluster_when_both_insight_and_fallback_raise(clean_db, monkeypatch):
    from core.db import get_session

    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())
    async with get_session() as session:
        session.add_all([source, run_row])
        await session.commit()

    cluster = await _make_cluster_with_articles(get_session, source, run_row, "Both Fail")

    async def boom(_):
        raise RuntimeError("always fails")

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", boom)
    monkeypatch.setattr("labeling.pipeline.generate_label", boom)

    result = await run()

    assert result["labeled"] == 0
    assert result["skipped"] == 1

    async with get_session() as session:
        row = await session.get(ArticleCluster, cluster.id)
        insight = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

    assert row.label is None
    assert insight is None


@pytest.mark.asyncio
async def test_run_skips_cluster_when_no_label_and_fallback_raises(clean_db, monkeypatch):
    from core.db import get_session

    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())
    async with get_session() as session:
        session.add_all([source, run_row])
        await session.commit()

    cluster = await _make_cluster_with_articles(get_session, source, run_row, "No Label Fallback Fail")

    async def no_label(_):
        return {"label": None, "what_happened": None, "parties_involved": None, "editorial_angle": None, "summary": None}

    async def boom_fallback(_):
        raise RuntimeError("fallback failed")

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", no_label)
    monkeypatch.setattr("labeling.pipeline.generate_label", boom_fallback)

    result = await run()

    assert result["labeled"] == 0
    assert result["skipped"] == 1

    async with get_session() as session:
        row = await session.get(ArticleCluster, cluster.id)
        insight = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

    assert row.label is None
    assert insight is None


@pytest.mark.asyncio
async def test_run_writes_user_need_distribution(clean_db, monkeypatch):
    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())
    async with get_session() as session:
        session.add_all([source, run_row])
        await session.flush()
        cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=2)
        session.add(cluster)
        await session.flush()
        for j in range(2):
            article = _article(source.id, f"Artikel {j}")
            session.add(article)
            await session.flush()
            session.add(
                ArticleClusterMember(cluster_id=cluster.id, article_id=article.id, relevance_score=1.0)
            )
        await session.commit()

    async def fake(_reps):
        return {
            "label": "Topik uji",
            "what_happened": "Sesuatu terjadi.",
            "parties_involved": ["A", "B"],
            "editorial_angle": "Sudut.",
            "summary": ["x"],
            "desk_category": "Politik",
            "user_need_category": None,
            "article_needs": [["Update me", "Give me perspective"], ["Update me"]],
        }

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", fake)

    await run()

    async with get_session() as session:
        row = (await session.execute(select(ClusterInsight))).scalars().one()
    assert row.user_need_distribution["Update me"] == 2
    assert row.user_need_reps_tagged == 2
    assert row.user_need_category == "Update me"   # dominant, not the (None) holistic field


@pytest.mark.asyncio
async def test_upsert_insight_does_not_overwrite_existing_with_none(clean_db):
    """Non-destructive: calling _upsert_insight with None args preserves existing values."""
    run_row = ClusterRun(id=uuid.uuid4())

    async with get_session() as session:
        session.add(run_row)
        await session.flush()
        cluster = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=1
        )
        session.add(cluster)
        await session.flush()
        insight = ClusterInsight(
            cluster_id=cluster.id,
            what_happened="Initial what happened",
            editorial_angle="Initial angle",
            summary=["Initial claim"],
        )
        session.add(insight)
        await session.commit()

    async with get_session() as session:
        await _upsert_insight(session, cluster.id, None, None, None, None)
        await session.commit()

    async with get_session() as session:
        row = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

    assert row is not None
    assert row.what_happened == "Initial what happened", "Non-null value must not be overwritten"
    assert row.editorial_angle == "Initial angle", "Non-null value must not be overwritten"
    assert row.summary == ["Initial claim"], "Non-null value must not be overwritten"


@pytest.mark.asyncio
async def test_upsert_insight_overwrites_with_non_none(clean_db):
    """Non-destructive: non-None args do update the field."""
    run_row = ClusterRun(id=uuid.uuid4())

    async with get_session() as session:
        session.add(run_row)
        await session.flush()
        cluster = ArticleCluster(
            id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=1
        )
        session.add(cluster)
        await session.flush()
        insight = ClusterInsight(
            cluster_id=cluster.id,
            what_happened="Old",
            editorial_angle="Old angle",
        )
        session.add(insight)
        await session.commit()

    async with get_session() as session:
        await _upsert_insight(session, cluster.id, "New", None, "New angle", None)
        await session.commit()

    async with get_session() as session:
        row = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one_or_none()

    assert row.what_happened == "New"
    assert row.editorial_angle == "New angle"
