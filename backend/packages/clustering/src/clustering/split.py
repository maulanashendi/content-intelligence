import logging
import uuid

import numpy as np
from core.config import settings
from core.db import get_session
from core.models import ArticleCluster, ArticleClusterMember, ArticleEmbedding
from sqlalchemy import delete, func, select

from clustering.clusterer import cluster as hdbscan_cluster

logger = logging.getLogger(__name__)


async def run() -> int:
    candidates = await _load_candidates()
    split_count = 0
    for cluster_id, run_id in candidates:
        did_split = await _split_cluster(cluster_id, run_id)
        if did_split:
            split_count += 1
    logger.info("cluster_split split=%d clusters", split_count)
    return split_count


async def _load_candidates() -> list[tuple[uuid.UUID, uuid.UUID]]:
    async with get_session() as session:
        avg_relevance = func.avg(ArticleClusterMember.relevance_score)
        stmt = (
            select(ArticleCluster.id, ArticleCluster.run_id)
            .join(ArticleClusterMember, ArticleClusterMember.cluster_id == ArticleCluster.id)
            .where(
                ArticleCluster.is_current.is_(True),
                ArticleCluster.parent_cluster_id.is_(None),
                ArticleCluster.member_count >= settings.cluster_split_min_member_count,
            )
            .group_by(ArticleCluster.id)
            .having(avg_relevance < settings.cluster_split_min_avg_relevance)
        )
        rows = (await session.execute(stmt)).all()
    return [(row.id, row.run_id) for row in rows]


async def _split_cluster(cluster_id: uuid.UUID, run_id: uuid.UUID) -> bool:
    async with get_session() as session:
        stmt = (
            select(ArticleClusterMember.article_id, ArticleEmbedding.embedding)
            .join(ArticleEmbedding, ArticleEmbedding.article_id == ArticleClusterMember.article_id)
            .where(
                ArticleClusterMember.cluster_id == cluster_id,
                ArticleEmbedding.embedding.isnot(None),
            )
        )
        rows = (await session.execute(stmt)).all()

    if not rows:
        return False

    article_ids = [r.article_id for r in rows]
    embeddings = np.array([r.embedding for r in rows], dtype=np.float32)

    labels, probs = hdbscan_cluster(embeddings)
    unique_labels = sorted(set(labels.tolist()) - {-1})

    if len(unique_labels) < 2:
        return False

    noise_ratio = float((labels == -1).sum()) / len(labels)
    if noise_ratio > settings.cluster_split_max_noise_ratio:
        logger.info(
            "cluster_split skipped cluster=%s noise_ratio=%.2f exceeds threshold",
            cluster_id,
            noise_ratio,
        )
        return False

    async with get_session() as session, session.begin():
        for sub_label in unique_labels:
            mask = labels == sub_label
            sub_indices = np.where(mask)[0]
            sub_probs = probs[mask]
            sub_embeddings = embeddings[mask]
            sub_centroid = sub_embeddings.mean(axis=0).tolist()

            sub_cluster = ArticleCluster(
                run_id=run_id,
                parent_cluster_id=cluster_id,
                centroid=sub_centroid,
                member_count=len(sub_indices),
                is_current=True,
            )
            session.add(sub_cluster)
            await session.flush()

            for idx, prob in zip(sub_indices, sub_probs, strict=True):
                session.add(
                    ArticleClusterMember(
                        cluster_id=sub_cluster.id,
                        article_id=article_ids[int(idx)],
                        relevance_score=float(prob),
                    )
                )

        # Parent becomes a label shell — members move to children
        await session.execute(
            delete(ArticleClusterMember).where(ArticleClusterMember.cluster_id == cluster_id)
        )

    logger.info(
        "cluster_split split cluster=%s into %d sub-clusters", cluster_id, len(unique_labels)
    )
    return True
