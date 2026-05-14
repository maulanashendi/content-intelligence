import logging
import uuid

import numpy as np
from core.config import settings
from core.db import get_session
from core.models import ArticleCluster, ArticleClusterMember, ArticleEmbedding
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import delete, select, update

logger = logging.getLogger(__name__)


async def run() -> int:
    core_vectors, member_counts = await _load_core_vectors()
    if len(core_vectors) < 2:
        return 0

    pairs = _find_merge_pairs(core_vectors, member_counts, settings.cluster_merge_similarity_threshold)
    if not pairs:
        return 0

    for small_id, large_id in pairs:
        await _merge_into(small_id, large_id)

    logger.info("cluster_merge merged=%d pairs", len(pairs))
    return len(pairs)


async def _load_core_vectors() -> tuple[dict[uuid.UUID, np.ndarray], dict[uuid.UUID, int]]:
    top_k = settings.cluster_merge_top_k
    async with get_session() as session:
        # Load top-k members by relevance_score for each current top-level cluster
        stmt = (
            select(
                ArticleClusterMember.cluster_id,
                ArticleEmbedding.embedding,
                ArticleClusterMember.relevance_score,
            )
            .join(ArticleEmbedding, ArticleEmbedding.article_id == ArticleClusterMember.article_id)
            .join(ArticleCluster, ArticleCluster.id == ArticleClusterMember.cluster_id)
            .where(
                ArticleCluster.is_current.is_(True),
                ArticleCluster.parent_cluster_id.is_(None),
                ArticleEmbedding.embedding.isnot(None),
            )
            .order_by(
                ArticleClusterMember.cluster_id,
                ArticleClusterMember.relevance_score.desc(),
            )
        )
        rows = (await session.execute(stmt)).all()

        cluster_stmt = select(ArticleCluster.id, ArticleCluster.member_count).where(
            ArticleCluster.is_current.is_(True),
            ArticleCluster.parent_cluster_id.is_(None),
        )
        cluster_rows = (await session.execute(cluster_stmt)).all()

    member_counts: dict[uuid.UUID, int] = {
        row.id: (row.member_count or 0) for row in cluster_rows
    }

    # Group embeddings per cluster, keeping top-k by relevance
    cluster_embeddings: dict[uuid.UUID, list[tuple[float, list[float]]]] = {}
    for row in rows:
        cid = row.cluster_id
        cluster_embeddings.setdefault(cid, [])
        if len(cluster_embeddings[cid]) < top_k:
            cluster_embeddings[cid].append((row.relevance_score or 0.0, row.embedding))

    core_vectors: dict[uuid.UUID, np.ndarray] = {}
    for cid, items in cluster_embeddings.items():
        vecs = np.array([emb for _, emb in items], dtype=np.float32)
        core_vectors[cid] = vecs.mean(axis=0)

    return core_vectors, member_counts


def _find_merge_pairs(
    core_vectors: dict[uuid.UUID, np.ndarray],
    member_counts: dict[uuid.UUID, int],
    threshold: float,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    ids = list(core_vectors.keys())
    matrix = np.stack([core_vectors[cid] for cid in ids])
    sim = cosine_similarity(matrix)

    # Collect candidate pairs sorted by similarity descending
    candidates: list[tuple[float, uuid.UUID, uuid.UUID]] = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if sim[i, j] >= threshold:
                candidates.append((sim[i, j], ids[i], ids[j]))
    candidates.sort(reverse=True)

    absorbed: set[uuid.UUID] = set()
    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    for _, a, b in candidates:
        if a in absorbed or b in absorbed:
            continue
        small, large = (a, b) if (member_counts.get(a, 0) <= member_counts.get(b, 0)) else (b, a)
        pairs.append((small, large))
        absorbed.add(small)

    return pairs


async def _merge_into(small_id: uuid.UUID, large_id: uuid.UUID) -> None:
    async with get_session() as session, session.begin():
        # Move members to the surviving cluster
        await session.execute(
            update(ArticleClusterMember)
            .where(ArticleClusterMember.cluster_id == small_id)
            .values(cluster_id=large_id)
        )

        # Recompute centroid and member_count from all member embeddings
        stmt = (
            select(ArticleEmbedding.embedding)
            .join(ArticleClusterMember, ArticleClusterMember.article_id == ArticleEmbedding.article_id)
            .where(ArticleClusterMember.cluster_id == large_id)
            .where(ArticleEmbedding.embedding.isnot(None))
        )
        rows = (await session.execute(stmt)).all()
        embeddings = np.array([r.embedding for r in rows], dtype=np.float32)
        new_centroid = embeddings.mean(axis=0).tolist()
        new_count = len(rows)

        await session.execute(
            update(ArticleCluster)
            .where(ArticleCluster.id == large_id)
            .values(centroid=new_centroid, member_count=new_count)
        )

        await session.execute(
            delete(ArticleCluster).where(ArticleCluster.id == small_id)
        )

    logger.info("cluster_merge absorbed small=%s into large=%s", small_id, large_id)
