import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
from core.config import settings
from core.db import get_session
from core.models import (
    Article,
    ArticleCluster,
    ArticleClusterMember,
    ArticleEmbedding,
    ClusterAlgorithm,
    ClusterRun,
)
from sqlalchemy import delete, func, select, true, update

from clustering.clusterer import cluster as hdbscan_cluster
from clustering.merge import run as merge_run
from clustering.reducer import reduce as umap_reduce
from clustering.split import run as split_run

logger = logging.getLogger(__name__)


async def run() -> None:
    started_at = datetime.now(UTC).replace(tzinfo=None)
    embeddings, article_ids = await _load_recent_embeddings()

    if len(embeddings) == 0:
        logger.info("no embeddings found in the last %d days", settings.clustering_window_days)
        return

    logger.info("loaded %d embeddings, reducing dimensions", len(embeddings))
    reduced = await asyncio.to_thread(umap_reduce, embeddings)

    logger.info("running HDBSCAN clustering")
    labels, probs = await asyncio.to_thread(hdbscan_cluster, reduced)

    unique_labels = set(labels.tolist())
    unique_labels.discard(-1)
    logger.info(
        "found %d clusters (%d noise points)", len(unique_labels), int((labels == -1).sum())
    )

    if not unique_labels:
        logger.warning("clustering produced only noise points, skipping persist")
        return

    await _persist_clusters(started_at, labels, probs, embeddings, article_ids)

    merged = await merge_run()
    logger.info("merge complete merged=%d", merged)

    split = await split_run()
    logger.info("split complete split=%d", split)

    logger.info("clustering run complete")


async def _load_recent_embeddings() -> tuple[np.ndarray, list[uuid.UUID]]:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        days=settings.clustering_window_days
    )
    async with get_session() as session:
        stmt = (
            select(ArticleEmbedding.article_id, ArticleEmbedding.embedding)
            .join(Article, ArticleEmbedding.article_id == Article.id)
            .where(func.coalesce(Article.published_at, Article.created_at) >= cutoff)
            .where(ArticleEmbedding.embedding.isnot(None))
        )
        result = await session.execute(stmt)
        rows = result.all()

    if not rows:
        return np.array([]), []

    article_ids = [row[0] for row in rows]
    embeddings = np.array([row[1] for row in rows], dtype=np.float32)
    return embeddings, article_ids


async def _persist_clusters(
    started_at: datetime,
    labels: np.ndarray,
    probs: np.ndarray,
    embeddings: np.ndarray,
    article_ids: list[uuid.UUID],
) -> None:
    params = {
        "umap_n_components": settings.umap_target_dimensions,
        "umap_random_state": settings.umap_random_state,
        "hdbscan_min_cluster_size": settings.hdbscan_min_cluster_size,
        "window_days": settings.clustering_window_days,
    }

    async with get_session() as session, session.begin():
        await session.execute(
            update(ArticleCluster)
            .where(ArticleCluster.is_current == true())
            .values(is_current=False)
        )

        cluster_run = ClusterRun(
            algorithm=ClusterAlgorithm.hdbscan,
            params=params,
            started_at=started_at,
            finished_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(cluster_run)
        await session.flush()

        unique_labels = sorted(set(labels.tolist()) - {-1})

        for cluster_label in unique_labels:
            mask = labels == cluster_label
            member_indices = np.where(mask)[0]
            member_probs = probs[mask]
            cluster_embeddings = embeddings[mask]

            centroid = cluster_embeddings.mean(axis=0).tolist()

            cluster = ArticleCluster(
                run_id=cluster_run.id,
                centroid=centroid,
                member_count=len(member_indices),
                is_current=True,
            )
            session.add(cluster)
            await session.flush()

            for idx, prob in zip(member_indices, member_probs, strict=True):
                session.add(
                    ArticleClusterMember(
                        cluster_id=cluster.id,
                        article_id=article_ids[int(idx)],
                        relevance_score=float(prob),
                    )
                )


async def prune_old_cluster_runs(keep: int | None = None) -> int:
    """Delete cluster runs beyond the `keep` most recent, cascading to their
    clusters, members, and insights (requires the FK ON DELETE CASCADE migration).

    Safe by construction: it builds an explicit keep-set (the N newest runs plus
    every run that still owns `is_current` clusters), refuses to act if that set
    is empty, and only ever issues `DELETE ... WHERE id IN (<materialized old ids>)`.
    There is no `NOT IN (<subquery>)` against the table, so an empty or buggy keep
    query can never escalate into a full-table wipe; the served run is never pruned.
    """
    keep = settings.cluster_run_retention_count if keep is None else keep
    if keep < 1:
        logger.warning("prune skipped: retention count %d < 1", keep)
        return 0

    async with get_session() as session, session.begin():
        recent_ids = set(
            (
                await session.execute(
                    select(ClusterRun.id)
                    .order_by(
                        func.coalesce(ClusterRun.finished_at, ClusterRun.started_at).desc(),
                        ClusterRun.id.desc(),
                    )
                    .limit(keep)
                )
            )
            .scalars()
            .all()
        )
        served_ids = set(
            (
                await session.execute(
                    select(ArticleCluster.run_id).where(ArticleCluster.is_current == true()).distinct()
                )
            )
            .scalars()
            .all()
        )
        keep_ids = recent_ids | served_ids
        if not keep_ids:
            logger.warning("prune aborted: keep-set empty, refusing to delete any run")
            return 0

        old_ids = list(
            (
                await session.execute(select(ClusterRun.id).where(ClusterRun.id.notin_(keep_ids)))
            )
            .scalars()
            .all()
        )
        if not old_ids:
            logger.info("prune: nothing to delete (kept=%d runs)", len(keep_ids))
            return 0

        await session.execute(delete(ClusterRun).where(ClusterRun.id.in_(old_ids)))

    logger.info("prune complete deleted_runs=%d kept_runs=%d", len(old_ids), len(keep_ids))
    return len(old_ids)
