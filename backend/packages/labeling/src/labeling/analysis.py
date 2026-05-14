import logging
import uuid

from core.db import get_session
from core.models import Article, ArticleCluster, ArticleClusterMember, ClusterInsight
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from labeling.llm import deduplicate_claims, extract_article_claims

logger = logging.getLogger(__name__)


async def _load_cluster_articles(
    session: AsyncSession,
    cluster_id: uuid.UUID,
) -> list[tuple[uuid.UUID, str, str]]:
    stmt = (
        select(Article.id, Article.title, Article.content)
        .join(ArticleClusterMember, ArticleClusterMember.article_id == Article.id)
        .where(
            ArticleClusterMember.cluster_id == cluster_id,
            Article.content.is_not(None),
        )
        .order_by(Article.published_at.desc().nullslast())
    )
    result = await session.execute(stmt)
    return [(row.id, row.title or "", row.content or "") for row in result.all()]


async def _find_cached_claims(
    session: AsyncSession,
    article_id: uuid.UUID,
) -> tuple[str | None, list[str]] | None:
    stmt = select(Article.main_entity, Article.information_claims).where(Article.id == article_id)
    row = (await session.execute(stmt)).one_or_none()
    if row is None or row.information_claims is None:
        return None
    return row.main_entity, row.information_claims


async def run() -> dict[str, int]:
    analyzed = 0
    skipped = 0

    async with get_session() as session:
        clusters_stmt = (
            select(ArticleCluster)
            .where(ArticleCluster.is_current.is_(True))
            .order_by(ArticleCluster.member_count.desc())
        )
        clusters = list((await session.execute(clusters_stmt)).scalars().all())
        logger.info("starting article analysis", extra={"cluster_count": len(clusters)})

        for cluster in clusters:
            articles = await _load_cluster_articles(session, cluster.id)
            if not articles:
                logger.warning(
                    "cluster has no articles with content",
                    extra={"cluster_id": str(cluster.id)},
                )
                skipped += 1
                continue

            all_claims: list[list[str]] = []

            for article_id, title, content in articles:
                cached = await _find_cached_claims(session, article_id)
                if cached is not None:
                    main_entity, information_claims = cached
                    logger.debug("cache hit", extra={"article_id": str(article_id)})
                else:
                    try:
                        result = extract_article_claims(title, content)
                        main_entity = result["main_entity"]
                        information_claims = result["information_claims"]
                    except Exception:
                        logger.exception(
                            "failed to extract claims",
                            extra={"article_id": str(article_id)},
                        )
                        continue

                    await session.execute(
                        update(Article)
                        .where(Article.id == article_id)
                        .values(main_entity=main_entity, information_claims=information_claims)
                    )

                if information_claims:
                    all_claims.append(information_claims)

            if not all_claims:
                skipped += 1
                continue

            try:
                unique_claims = deduplicate_claims(all_claims)
            except Exception:
                logger.exception(
                    "failed to deduplicate claims",
                    extra={"cluster_id": str(cluster.id)},
                )
                skipped += 1
                continue

            insight = (
                await session.execute(
                    select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
                )
            ).scalar_one_or_none()

            if insight is not None:
                insight.summary = unique_claims

            analyzed += 1
            logger.info(
                "cluster analyzed",
                extra={"cluster_id": str(cluster.id), "claim_count": len(unique_claims)},
            )

        await session.commit()

    result = {"analyzed": analyzed, "skipped": skipped}
    logger.info("analysis complete", extra=result)
    return result
