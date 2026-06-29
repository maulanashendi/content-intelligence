import uuid

import pytest
from core.db import get_session
from core.models import ArticleCluster, ClusterInsight, ClusterRun
from labeling.pipeline import _upsert_insight
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def test_upsert_insight_persists_classification(clean_db) -> None:
    async with get_session() as session:
        run = ClusterRun(id=uuid.uuid4())
        cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, is_current=True)
        session.add_all([run, cluster])
        await session.flush()

        await _upsert_insight(
            session,
            cluster.id,
            what_happened=None,
            parties_involved=None,
            editorial_angle=None,
            summary=None,
            desk_category="Politik",
            user_need_category="Update me",
        )
        await session.commit()

        row = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one()
        assert row.desk_category == "Politik"
        assert row.user_need_category == "Update me"


async def test_upsert_insight_none_classification_left_unset(clean_db) -> None:
    async with get_session() as session:
        run = ClusterRun(id=uuid.uuid4())
        cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, is_current=True)
        session.add_all([run, cluster])
        await session.flush()

        await _upsert_insight(
            session, cluster.id, None, None, None, None,
            desk_category=None, user_need_category=None,
        )
        await session.commit()

        row = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one()
        assert row.desk_category is None
        assert row.user_need_category is None
