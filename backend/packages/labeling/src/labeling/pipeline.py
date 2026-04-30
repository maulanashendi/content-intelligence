import logging
import uuid

from core.db import get_session
from core.models import Article, ArticleCluster, ArticleClusterMember
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from labeling.llm import generate_label

logger = logging.getLogger(__name__)

TOP_ARTICLES_PER_CLUSTER = 5


async def _load_current_clusters(session: AsyncSession) -> list[ArticleCluster]:
    stmt = (
        select(ArticleCluster)
        .where(ArticleCluster.is_current.is_(True))
        .order_by(ArticleCluster.member_count.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _get_top_articles(
    session: AsyncSession,
    cluster_id: uuid.UUID,
) -> list[dict[str, str | None]]:
    stmt = (
        select(Article.title, Article.first_paragraph)
        .join(ArticleClusterMember, ArticleClusterMember.article_id == Article.id)
        .where(ArticleClusterMember.cluster_id == cluster_id)
        .order_by(ArticleClusterMember.relevance_score.desc())
        .limit(TOP_ARTICLES_PER_CLUSTER)
    )
    result = await session.execute(stmt)
    return [{"title": row.title, "first_paragraph": row.first_paragraph} for row in result.all()]


async def run() -> dict[str, int]:
    labeled = 0
    skipped = 0

    async with get_session() as session:
        clusters = await _load_current_clusters(session)
        logger.info("found current clusters to label", extra={"cluster_count": len(clusters)})

        for cluster in clusters:
            articles = await _get_top_articles(session, cluster.id)
            if not articles:
                logger.warning("cluster has no articles", extra={"cluster_id": str(cluster.id)})
                skipped += 1
                continue

            try:
                label = generate_label(articles)
            except Exception:
                logger.exception(
                    "failed to generate cluster label", extra={"cluster_id": str(cluster.id)}
                )
                skipped += 1
                continue

            cluster.label = label
            labeled += 1
            logger.info("cluster labeled", extra={"cluster_id": str(cluster.id), "label": label})

        await session.commit()

    result = {"labeled": labeled, "skipped": skipped}
    logger.info("labeling complete", extra=result)
    return result
