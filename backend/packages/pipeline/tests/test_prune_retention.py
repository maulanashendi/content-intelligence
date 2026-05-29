import uuid
from datetime import datetime, timedelta

import pytest
from clustering.pipeline import prune_old_cluster_runs
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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.usefixtures("clean_db")

_BASE = datetime(2026, 5, 1, 6, 0, 0)


async def _source(session: AsyncSession) -> uuid.UUID:
    src = ContentSource(
        id=uuid.uuid4(),
        name="Detik",
        url=f"https://detik-{uuid.uuid4()}.test",
        source_type=SourceType.rss,
    )
    session.add(src)
    await session.flush()
    return src.id


async def _make_run(
    session: AsyncSession, source_id: uuid.UUID, *, finished_at: datetime, is_current: bool
) -> uuid.UUID:
    """A run with one cluster that owns one member and one insight."""
    run = ClusterRun(id=uuid.uuid4(), started_at=finished_at, finished_at=finished_at)
    cluster = ArticleCluster(
        id=uuid.uuid4(), run_id=run.id, is_current=is_current, member_count=1
    )
    article = Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title="Article",
        url=f"https://detik.test/{uuid.uuid4()}",
        published_at=finished_at,
    )
    session.add_all([run, cluster, article])
    await session.flush()
    session.add(ArticleClusterMember(cluster_id=cluster.id, article_id=article.id))
    session.add(ClusterInsight(id=uuid.uuid4(), cluster_id=cluster.id))
    return run.id


async def _counts() -> dict[str, int]:
    async with get_session() as session:
        out = {}
        for name, model in (
            ("runs", ClusterRun),
            ("clusters", ArticleCluster),
            ("members", ArticleClusterMember),
            ("insights", ClusterInsight),
        ):
            out[name] = (
                await session.execute(select(func.count()).select_from(model))
            ).scalar_one()
        return out


async def test_prune_deletes_old_runs_and_cascades() -> None:
    async with get_session() as session:
        src = await _source(session)
        await _make_run(session, src, finished_at=_BASE - timedelta(days=3), is_current=False)
        await _make_run(session, src, finished_at=_BASE - timedelta(days=2), is_current=False)
        await _make_run(session, src, finished_at=_BASE, is_current=True)
        await session.commit()

    deleted = await prune_old_cluster_runs(keep=1)

    assert deleted == 2
    # Cascade: the two old runs took their clusters, members, and insights with them.
    assert await _counts() == {"runs": 1, "clusters": 1, "members": 1, "insights": 1}


async def test_prune_never_deletes_served_run_even_when_oldest() -> None:
    async with get_session() as session:
        src = await _source(session)
        served = await _make_run(
            session, src, finished_at=_BASE - timedelta(days=5), is_current=True
        )
        await _make_run(session, src, finished_at=_BASE - timedelta(days=1), is_current=False)
        newest = await _make_run(session, src, finished_at=_BASE, is_current=False)
        await session.commit()

    deleted = await prune_old_cluster_runs(keep=1)

    assert deleted == 1  # only the middle run (neither newest nor served)
    async with get_session() as session:
        surviving = set(
            (await session.execute(select(ClusterRun.id))).scalars().all()
        )
    assert served in surviving  # served run protected despite being the oldest
    assert newest in surviving


async def test_prune_noop_when_within_retention() -> None:
    async with get_session() as session:
        src = await _source(session)
        await _make_run(session, src, finished_at=_BASE - timedelta(days=1), is_current=False)
        await _make_run(session, src, finished_at=_BASE, is_current=True)
        await session.commit()

    deleted = await prune_old_cluster_runs(keep=5)

    assert deleted == 0
    assert (await _counts())["runs"] == 2


async def test_prune_returns_zero_on_empty_database() -> None:
    # Empty keep-set must abort, not wipe — the safety guard.
    deleted = await prune_old_cluster_runs(keep=3)
    assert deleted == 0
