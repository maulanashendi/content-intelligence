import uuid
from datetime import UTC, datetime, timedelta

import pytest
from core.config import settings
from core.db import get_session
from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ClusterRun,
    ContentSource,
    SourceType,
    TrendSignal,
    TrendSignalArticle,
)
from labeling.pipeline import _select_cluster_ids_for_labeling
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.usefixtures("clean_db")

_NOW = datetime.now(UTC).replace(tzinfo=None)


async def _make_cluster(
    session: AsyncSession,
    run_id: uuid.UUID,
    source_id: uuid.UUID,
    *,
    member_count: int,
    fresh_trends: int,
    stale_trends: int = 0,
) -> uuid.UUID:
    cluster = ArticleCluster(
        id=uuid.uuid4(), run_id=run_id, is_current=True, member_count=member_count
    )
    article = Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title="t",
        url=f"https://x.test/{uuid.uuid4()}",
        published_at=_NOW,
    )
    session.add_all([cluster, article])
    await session.flush()
    session.add(ArticleClusterMember(cluster_id=cluster.id, article_id=article.id))
    for offset, n in ((timedelta(hours=1), fresh_trends), (timedelta(hours=48), stale_trends)):
        for _ in range(n):
            ts = TrendSignal(
                id=uuid.uuid4(),
                keyword=f"k-{uuid.uuid4()}",
                interest_score=50.0,
                captured_at=_NOW - offset,
            )
            session.add(ts)
            await session.flush()
            session.add(TrendSignalArticle(trend_signal_id=ts.id, article_id=article.id))
    return cluster.id


async def _seed(session: AsyncSession) -> dict[str, uuid.UUID]:
    src = ContentSource(
        id=uuid.uuid4(),
        name="Detik",
        url=f"https://detik-{uuid.uuid4()}.test",
        source_type=SourceType.rss,
    )
    run = ClusterRun(id=uuid.uuid4())
    session.add_all([src, run])
    await session.flush()
    return {
        # a: top trend; b: second trend; c: no fresh trend but biggest; d: smallest
        "a": await _make_cluster(session, run.id, src.id, member_count=5, fresh_trends=2),
        "b": await _make_cluster(session, run.id, src.id, member_count=50, fresh_trends=1),
        "c": await _make_cluster(session, run.id, src.id, member_count=100, fresh_trends=0, stale_trends=3),
        "d": await _make_cluster(session, run.id, src.id, member_count=10, fresh_trends=0),
    }


async def test_caps_to_top_trend_then_member(monkeypatch) -> None:
    async with get_session() as session:
        ids = await _seed(session)
        await session.commit()

    monkeypatch.setattr(settings, "labeling_max_clusters", 2)
    async with get_session() as session:
        selected, total = await _select_cluster_ids_for_labeling(session)

    assert total == 4
    # Capped at 2: the two trend-matching clusters win; stale trends on c don't count.
    assert selected == [ids["a"], ids["b"]]


async def test_full_priority_order_when_under_cap(monkeypatch) -> None:
    async with get_session() as session:
        ids = await _seed(session)
        await session.commit()

    monkeypatch.setattr(settings, "labeling_max_clusters", 10)
    async with get_session() as session:
        selected, total = await _select_cluster_ids_for_labeling(session)

    assert total == 4
    # trend desc (a=2, b=1), then member_count desc among non-trending (c=100 > d=10)
    assert selected == [ids["a"], ids["b"], ids["c"], ids["d"]]
