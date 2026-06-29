import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from core.config import settings
from core.db import get_session
from core.models import Article, ArticleCluster, ArticleClusterMember, ArticleEmbedding, ClusterInsight
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.taxonomy import normalize_desk, normalize_user_need
from labeling.llm import generate_cluster_insight, generate_label

logger = logging.getLogger(__name__)

TOP_ARTICLES_PER_CLUSTER = 5
_SUB_CLUSTER_THRESHOLD = 0.90
_MAX_REPRESENTATIVES = 20


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]


def _sub_cluster(members: list[dict[str, Any]], threshold: float) -> list[list[int]]:
    n = len(members)
    mat = np.stack([m["embedding"] for m in members])
    sims = mat @ mat.T
    uf = _UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            if sims[i, j] >= threshold:
                uf.union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)
    return list(groups.values())


def _pick_representatives(
    members: list[dict[str, Any]], groups: list[list[int]], cap: int
) -> list[int]:
    reps = [max(g, key=lambda i: members[i]["relevance"]) for g in groups]
    if len(reps) <= cap:
        return reps
    sorted_reps = sorted(reps, key=lambda i: -members[i]["relevance"])
    selected = [sorted_reps[0]]
    remaining = sorted_reps[1:]
    while remaining and len(selected) < cap:
        best = None
        best_score = -1e9
        for r in remaining:
            sims = [float(members[r]["embedding"] @ members[s]["embedding"]) for s in selected]
            score = members[r]["relevance"] - max(sims)
            if score > best_score:
                best_score = score
                best = r
        if best is None:
            break
        selected.append(best)
        remaining.remove(best)
    return selected


async def _select_cluster_ids_for_labeling(
    session: AsyncSession,
) -> tuple[list[uuid.UUID], int]:
    """Current top-level cluster ids in labeling priority order, capped at
    settings.labeling_max_clusters.

    Priority: trend match (distinct trending keywords within scoring_trend_window_days
    that the cluster's articles hit) desc, then member_count desc. When a run produces
    more clusters than the cap, the Gemma budget is spent on the most newsworthy
    (trending) and largest clusters; the long tail is left unlabeled this run
    (still scored). Returns (selected_ids, total_current_count).
    """
    trend_window = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        days=settings.scoring_trend_window_days
    )
    sql = text(
        """
        SELECT c.id AS cluster_id
        FROM article_cluster c
        LEFT JOIN (
            SELECT m.cluster_id, COUNT(DISTINCT ts.keyword) AS trend_match_count
            FROM article_cluster_member m
            JOIN trend_signal_article tsa ON tsa.article_id = m.article_id
            JOIN trend_signal ts          ON ts.id = tsa.trend_signal_id
            WHERE ts.captured_at >= :trend_window
            GROUP BY m.cluster_id
        ) t ON t.cluster_id = c.id
        WHERE c.is_current = true
          AND NOT EXISTS (
              SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id
          )
        ORDER BY COALESCE(t.trend_match_count, 0) DESC,
                 COALESCE(c.member_count, 0) DESC,
                 c.id
        """
    )
    all_ids = [
        row.cluster_id
        for row in (await session.execute(sql, {"trend_window": trend_window})).all()
    ]
    return all_ids[: settings.labeling_max_clusters], len(all_ids)


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


async def _get_representative_articles(
    session: AsyncSession,
    cluster_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Sub-cluster at cosine ≥ 0.90, pick one rep per sub-group, MMR-cap at 20."""
    stmt = (
        select(
            Article.title,
            Article.first_paragraph,
            ArticleEmbedding.embedding,
            ArticleClusterMember.relevance_score,
        )
        .join(ArticleClusterMember, ArticleClusterMember.article_id == Article.id)
        .join(ArticleEmbedding, ArticleEmbedding.article_id == Article.id)
        .where(
            ArticleClusterMember.cluster_id == cluster_id,
            ArticleEmbedding.embedding.is_not(None),
        )
        .order_by(ArticleClusterMember.relevance_score.desc())
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        return []

    members: list[dict[str, Any]] = []
    for r in rows:
        emb = np.asarray(list(r.embedding), dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm == 0:
            continue
        members.append(
            {
                "title": r.title or "",
                "first_paragraph": r.first_paragraph or "",
                "embedding": emb / norm,
                "relevance": float(r.relevance_score) if r.relevance_score is not None else 0.0,
            }
        )

    if not members:
        return []

    groups = _sub_cluster(members, _SUB_CLUSTER_THRESHOLD)
    rep_indices = _pick_representatives(members, groups, _MAX_REPRESENTATIVES)
    return [members[i] for i in rep_indices]


async def _upsert_insight(
    session: AsyncSession,
    cluster_id: uuid.UUID,
    what_happened: str | None,
    parties_involved: list[str] | None,
    editorial_angle: str | None,
    summary: list[str] | None = None,
    desk_category: str | None = None,
    user_need_category: str | None = None,
) -> None:
    """Non-destructive: only overwrites a field when the new value is non-None."""
    insight = (
        await session.execute(
            select(ClusterInsight).where(ClusterInsight.cluster_id == cluster_id)
        )
    ).scalar_one_or_none()
    if insight is None:
        insight = ClusterInsight(cluster_id=cluster_id)
        session.add(insight)
    if what_happened is not None:
        insight.what_happened = what_happened
    if parties_involved is not None:
        insight.parties_involved = parties_involved
    if editorial_angle is not None:
        insight.editorial_angle = editorial_angle
    if summary is not None:
        insight.summary = summary
    if desk_category is not None:
        insight.desk_category = desk_category
    if user_need_category is not None:
        insight.user_need_category = user_need_category


async def run() -> dict[str, int]:
    labeled = 0
    skipped = 0

    async with get_session() as session:
        cluster_ids, total = await _select_cluster_ids_for_labeling(session)
    capped = total - len(cluster_ids)
    logger.info(
        "selected clusters to label",
        extra={"cluster_count": len(cluster_ids), "total_current": total, "capped": capped},
    )

    for cluster_id in cluster_ids:
        async with get_session() as session:
            reps = await _get_representative_articles(session, cluster_id)
            if not reps:
                reps = await _get_top_articles(session, cluster_id)

            if not reps:
                logger.warning("cluster has no articles", extra={"cluster_id": str(cluster_id)})
                skipped += 1
                continue

            articles_simple = [
                {"title": r.get("title"), "first_paragraph": r.get("first_paragraph")}
                for r in reps
            ]

            try:
                result = await generate_cluster_insight(reps)
            except Exception:
                logger.exception(
                    "failed to generate cluster insight",
                    extra={"cluster_id": str(cluster_id)},
                )
                result = {
                    "label": None,
                    "what_happened": None,
                    "parties_involved": None,
                    "editorial_angle": None,
                    "summary": None,
                }

            label = result.get("label")
            if not label:
                logger.warning(
                    "cluster llm output missing LABEL, attempting fallback",
                    extra={"cluster_id": str(cluster_id)},
                )
                try:
                    label = await generate_label(articles_simple)
                except Exception:
                    logger.exception(
                        "fallback generate_label also failed, skipping cluster",
                        extra={"cluster_id": str(cluster_id)},
                    )
                    skipped += 1
                    continue
                if not label:
                    logger.warning(
                        "fallback generate_label returned empty, skipping cluster",
                        extra={"cluster_id": str(cluster_id)},
                    )
                    skipped += 1
                    continue
                logger.warning(
                    "cluster labeled via fallback after missing LABEL",
                    extra={"cluster_id": str(cluster_id)},
                )
                # Partial insight from a no-label response is unreliable; reset to None
                # (non-destructive upsert means existing good values are preserved)
                result = {
                    "label": label,
                    "what_happened": None,
                    "parties_involved": None,
                    "editorial_angle": None,
                    "summary": None,
                }

            cluster_row = await session.get(ArticleCluster, cluster_id)
            if cluster_row is None:
                skipped += 1
                continue
            cluster_row.label = label
            await _upsert_insight(
                session,
                cluster_id,
                result.get("what_happened"),
                result.get("parties_involved"),
                result.get("editorial_angle"),
                result.get("summary"),
                desk_category=normalize_desk(result.get("desk_category")),
                user_need_category=normalize_user_need(result.get("user_need_category")),
            )
            await session.commit()

        labeled += 1
        logger.info(
            "cluster labeled",
            extra={
                "cluster_id": str(cluster_id),
                "label": label,
                "parties_count": len(result.get("parties_involved") or []),
            },
        )

    out = {"labeled": labeled, "skipped": skipped, "capped": capped}
    logger.info("labeling complete", extra=out)
    return out
