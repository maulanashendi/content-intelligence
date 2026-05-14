from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from core.config import settings
from core.db import get_session
from core.models import ClusterInsight
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from scoring.velocity import compute_trend_velocity


@dataclass(slots=True)
class ClusterFacts:
    count_24h: int = 0
    count_7d: int = 0
    competitor_count: int = 0
    trend_match_count: int = 0
    tempo_covered: bool = False
    last_internal_days_ago: int | None = None
    underperformed: bool = False


async def run(*, now: datetime | None = None) -> int:
    current_time = _normalize_now(now)
    t24h = current_time - timedelta(hours=24)
    t7d = current_time - timedelta(days=7)

    async with get_session() as session:
        facts_by_cluster: dict[UUID, ClusterFacts] = {}

        await _load_article_facts(session, facts_by_cluster, t24h, t7d, current_time)
        await _load_trend_match(session, facts_by_cluster, t24h)
        await _load_underperformed(session, facts_by_cluster)

        if not facts_by_cluster:
            return 0

        rows = [
            {
                "cluster_id": cid,
                "trend_velocity": compute_trend_velocity(f.count_24h, f.count_7d),
                "competitor_count": f.competitor_count,
                "trend_match_count": f.trend_match_count,
                "tempo_covered": f.tempo_covered,
                "last_internal_days_ago": f.last_internal_days_ago,
                "underperformed": f.underperformed,
                "calculated_at": current_time,
            }
            for cid, f in facts_by_cluster.items()
        ]

        stmt = pg_insert(ClusterInsight).values(rows)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["cluster_id"],
                set_={
                    "trend_velocity": stmt.excluded.trend_velocity,
                    "competitor_count": stmt.excluded.competitor_count,
                    "trend_match_count": stmt.excluded.trend_match_count,
                    "tempo_covered": stmt.excluded.tempo_covered,
                    "last_internal_days_ago": stmt.excluded.last_internal_days_ago,
                    "underperformed": stmt.excluded.underperformed,
                    "calculated_at": stmt.excluded.calculated_at,
                },
            )
        )
        await session.commit()

    return len(rows)


async def _load_article_facts(
    session: AsyncSession,
    facts: dict[UUID, ClusterFacts],
    t24h: datetime,
    t7d: datetime,
    now: datetime,
) -> None:
    sql = text(
        """
        SELECT
            m.cluster_id AS cluster_id,
            COUNT(*) FILTER (WHERE a.published_at >= :t24h) AS count_24h,
            COUNT(*) FILTER (WHERE a.published_at >= :t7d)  AS count_7d,
            COUNT(DISTINCT cs.id) FILTER (WHERE cs.source_type = 'rss') AS competitor_count,
            BOOL_OR(cs.source_type = 'internal') AS tempo_covered,
            FLOOR(EXTRACT(EPOCH FROM (
                :now - MAX(COALESCE(a.published_at, a.created_at)) FILTER (WHERE cs.source_type = 'internal')
            )) / 86400)::int AS last_internal_days_ago
        FROM article_cluster_member m
        JOIN article a         ON a.id = m.article_id
        JOIN content_source cs ON cs.id = a.source_id
        JOIN article_cluster c ON c.id = m.cluster_id AND c.is_current = true
        WHERE NOT EXISTS (
            SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id
        )
        GROUP BY m.cluster_id
        """
    )
    rows = (await session.execute(sql, {"t24h": t24h, "t7d": t7d, "now": now})).mappings()
    for row in rows:
        cid = row["cluster_id"]
        f = facts.setdefault(cid, ClusterFacts())
        f.count_24h = int(row["count_24h"] or 0)
        f.count_7d = int(row["count_7d"] or 0)
        f.competitor_count = int(row["competitor_count"] or 0)
        f.tempo_covered = bool(row["tempo_covered"])
        last = row["last_internal_days_ago"]
        f.last_internal_days_ago = int(last) if last is not None else None


async def _load_trend_match(
    session: AsyncSession,
    facts: dict[UUID, ClusterFacts],
    t24h: datetime,
) -> None:
    # trend_signal exposes captured_at (NOT fetched_at); see core/models.py:246.
    sql = text(
        """
        SELECT
            m.cluster_id AS cluster_id,
            COUNT(DISTINCT tsa.trend_signal_id) AS trend_match_count
        FROM article_cluster_member m
        JOIN trend_signal_article tsa ON tsa.article_id = m.article_id
        JOIN trend_signal ts          ON ts.id = tsa.trend_signal_id
        JOIN article_cluster c        ON c.id = m.cluster_id AND c.is_current = true
        WHERE ts.captured_at >= :t24h
          AND NOT EXISTS (
              SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id
          )
        GROUP BY m.cluster_id
        """
    )
    rows = (await session.execute(sql, {"t24h": t24h})).mappings()
    for row in rows:
        cid = row["cluster_id"]
        f = facts.setdefault(cid, ClusterFacts())
        f.trend_match_count = int(row["trend_match_count"] or 0)


async def _load_underperformed(
    session: AsyncSession,
    facts: dict[UUID, ClusterFacts],
) -> None:
    # AND across all three thresholds (D27 user decision; current coverage.py
    # used OR — that file is being deleted). avg_position is the GSC column
    # name (core/models.py:147).
    sql = text(
        """
        SELECT
            m.cluster_id AS cluster_id,
            BOOL_OR(
                g.impressions > :imp_thr
                AND g.avg_position > :pos_thr
                AND g.ctr < :ctr_thr
            ) AS underperformed
        FROM article_cluster_member m
        JOIN article a            ON a.id = m.article_id
        JOIN content_source cs    ON cs.id = a.source_id AND cs.source_type = 'internal'
        JOIN article_gsc_metric g ON g.article_id = a.id
        JOIN article_cluster c    ON c.id = m.cluster_id AND c.is_current = true
        WHERE NOT EXISTS (
            SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id
        )
        GROUP BY m.cluster_id
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "imp_thr": settings.gsc_underperform_impressions_min,
                "pos_thr": settings.gsc_underperform_position_min,
                "ctr_thr": settings.gsc_underperform_ctr_max,
            },
        )
    ).mappings()
    for row in rows:
        cid = row["cluster_id"]
        f = facts.setdefault(cid, ClusterFacts())
        f.underperformed = bool(row["underperformed"])


def _normalize_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(tzinfo=None)
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value
