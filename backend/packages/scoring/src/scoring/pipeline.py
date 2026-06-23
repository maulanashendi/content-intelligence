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

from scoring.demand import classify_demand
from scoring.performance import classify_performance
from scoring.velocity import compute_trend_velocity

# asyncpg hard limit is 32767 params/query; 18 cols × 1000 rows = 18000 — safe margin.
_UPSERT_BATCH = 1000


@dataclass(slots=True)
class ClusterFacts:
    count_24h: int = 0
    count_7d: int = 0
    competitor_count: int = 0
    trend_match_count: int = 0
    weighted_trend_score: float = 0.0
    tempo_covered: bool = False
    last_internal_days_ago: int | None = None
    underperformed: bool = False
    gsc_impressions: int = 0
    gsc_clicks: int = 0
    gsc_ctr: float | None = None
    gsc_avg_position: float | None = None
    competitor_freshness_days: int | None = None
    # Set by classify_demand / classify_performance after DB load
    demand_score: float = 0.0
    high_demand: bool = False
    performance_level: str = "none"
    editorial_quadrant: str = "ignore"


async def run(*, now: datetime | None = None) -> int:
    current_time = _normalize_now(now)
    t24h = current_time - timedelta(hours=24)
    t7d = current_time - timedelta(days=7)
    trend_window = current_time - timedelta(days=settings.scoring_trend_window_days)

    async with get_session() as session:
        facts_by_cluster: dict[UUID, ClusterFacts] = {}

        await _load_article_facts(session, facts_by_cluster, t24h, t7d, current_time)
        await _load_trend_match(session, facts_by_cluster, trend_window)
        await _load_weighted_trend_score(session, facts_by_cluster, trend_window)
        await _load_underperformed(session, facts_by_cluster)
        await _load_gsc_signals(session, facts_by_cluster)
        await _load_competitor_freshness_days(session, facts_by_cluster, current_time)

        if not facts_by_cluster:
            return 0

        classify_demand(facts_by_cluster, settings.demand_high_percentile)
        classify_performance(facts_by_cluster, settings.performance_high_percentile)
        for f in facts_by_cluster.values():
            f.editorial_quadrant = _compute_quadrant(f.high_demand, f.performance_level)

        rows = [
            {
                "cluster_id": cid,
                "trend_velocity": compute_trend_velocity(f.count_24h, f.count_7d),
                "competitor_count": f.competitor_count,
                "trend_match_count": f.trend_match_count,
                "weighted_trend_score": f.weighted_trend_score,
                "tempo_covered": f.tempo_covered,
                "last_internal_days_ago": f.last_internal_days_ago,
                "underperformed": f.underperformed,
                "gsc_impressions": f.gsc_impressions,
                "gsc_clicks": f.gsc_clicks,
                "gsc_ctr": f.gsc_ctr,
                "gsc_avg_position": f.gsc_avg_position,
                "competitor_freshness_days": f.competitor_freshness_days,
                "demand_score": f.demand_score,
                "high_demand": f.high_demand,
                "performance_level": f.performance_level,
                "editorial_quadrant": f.editorial_quadrant,
                "calculated_at": current_time,
            }
            for cid, f in facts_by_cluster.items()
        ]

        for i in range(0, len(rows), _UPSERT_BATCH):
            batch = rows[i : i + _UPSERT_BATCH]
            stmt = pg_insert(ClusterInsight).values(batch)
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["cluster_id"],
                    set_={
                        "trend_velocity": stmt.excluded.trend_velocity,
                        "competitor_count": stmt.excluded.competitor_count,
                        "trend_match_count": stmt.excluded.trend_match_count,
                        "weighted_trend_score": stmt.excluded.weighted_trend_score,
                        "tempo_covered": stmt.excluded.tempo_covered,
                        "last_internal_days_ago": stmt.excluded.last_internal_days_ago,
                        "underperformed": stmt.excluded.underperformed,
                        "gsc_impressions": stmt.excluded.gsc_impressions,
                        "gsc_clicks": stmt.excluded.gsc_clicks,
                        "gsc_ctr": stmt.excluded.gsc_ctr,
                        "gsc_avg_position": stmt.excluded.gsc_avg_position,
                        "competitor_freshness_days": stmt.excluded.competitor_freshness_days,
                        "demand_score": stmt.excluded.demand_score,
                        "high_demand": stmt.excluded.high_demand,
                        "performance_level": stmt.excluded.performance_level,
                        "editorial_quadrant": stmt.excluded.editorial_quadrant,
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
            COUNT(*) FILTER (WHERE COALESCE(a.published_at, a.created_at) >= :t24h) AS count_24h,
            COUNT(*) FILTER (WHERE COALESCE(a.published_at, a.created_at) >= :t7d)  AS count_7d,
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
    trend_window: datetime,
) -> None:
    # Count distinct trending *keywords* (not signal rows) so that the daemon's
    # 10-minute poll cadence — which creates one trend_signal row per keyword per
    # poll — does not inflate the count. captured_at (NOT fetched_at) is the
    # authoritative recency field; see core/models.py:246.
    sql = text(
        """
        SELECT
            m.cluster_id AS cluster_id,
            COUNT(DISTINCT ts.keyword) AS trend_match_count
        FROM article_cluster_member m
        JOIN trend_signal_article tsa ON tsa.article_id = m.article_id
        JOIN trend_signal ts          ON ts.id = tsa.trend_signal_id
        JOIN article_cluster c        ON c.id = m.cluster_id AND c.is_current = true
        WHERE ts.captured_at >= :trend_window
          AND NOT EXISTS (
              SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id
          )
        GROUP BY m.cluster_id
        """
    )
    rows = (await session.execute(sql, {"trend_window": trend_window})).mappings()
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


async def _load_weighted_trend_score(
    session: AsyncSession,
    facts: dict[UUID, ClusterFacts],
    trend_window: datetime,
) -> None:
    # Sum the per-keyword peak interest score — take MAX across the many capture
    # rows a single keyword accumulates during the 10-minute poll window, then
    # sum across distinct keywords so repeated captures don't inflate the score.
    sql = text(
        """
        SELECT cluster_id, SUM(kw_interest) AS weighted_trend_score
        FROM (
            SELECT m.cluster_id, ts.keyword, MAX(ts.interest_score) AS kw_interest
            FROM article_cluster_member m
            JOIN trend_signal_article tsa ON tsa.article_id = m.article_id
            JOIN trend_signal ts          ON ts.id = tsa.trend_signal_id
            JOIN article_cluster c        ON c.id = m.cluster_id AND c.is_current = true
            WHERE ts.captured_at >= :trend_window
              AND NOT EXISTS (
                  SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id
              )
            GROUP BY m.cluster_id, ts.keyword
        ) per_kw
        GROUP BY cluster_id
        """
    )
    rows = (await session.execute(sql, {"trend_window": trend_window})).mappings()
    for row in rows:
        cid = row["cluster_id"]
        f = facts.setdefault(cid, ClusterFacts())
        f.weighted_trend_score = float(row["weighted_trend_score"] or 0.0)


async def _load_gsc_signals(
    session: AsyncSession,
    facts: dict[UUID, ClusterFacts],
) -> None:
    # LATERAL picks the most recent GSC period per article to avoid double-counting
    # when multiple periods are stored. Aggregates across all internal members then
    # computes impression-weighted avg_position at the cluster level.
    sql = text(
        """
        SELECT
            m.cluster_id,
            COALESCE(SUM(latest_g.impressions), 0) AS gsc_impressions,
            COALESCE(SUM(latest_g.clicks), 0)      AS gsc_clicks,
            CASE
                WHEN COALESCE(SUM(latest_g.impressions), 0) > 0
                THEN SUM(latest_g.clicks)::float / SUM(latest_g.impressions)
                ELSE NULL
            END AS gsc_ctr,
            CASE
                WHEN COALESCE(SUM(latest_g.impressions), 0) > 0
                THEN SUM(latest_g.avg_position * latest_g.impressions) / SUM(latest_g.impressions)
                ELSE NULL
            END AS gsc_avg_position
        FROM article_cluster_member m
        JOIN article a         ON a.id = m.article_id
        JOIN content_source cs ON cs.id = a.source_id AND cs.source_type = 'internal'
        LEFT JOIN LATERAL (
            SELECT impressions, clicks, avg_position
            FROM article_gsc_metric
            WHERE article_id = a.id
            ORDER BY period_end DESC
            LIMIT 1
        ) latest_g ON true
        JOIN article_cluster c ON c.id = m.cluster_id AND c.is_current = true
        WHERE NOT EXISTS (
            SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id
        )
        GROUP BY m.cluster_id
        """
    )
    rows = (await session.execute(sql)).mappings()
    for row in rows:
        cid = row["cluster_id"]
        f = facts.setdefault(cid, ClusterFacts())
        f.gsc_impressions = int(row["gsc_impressions"] or 0)
        f.gsc_clicks = int(row["gsc_clicks"] or 0)
        f.gsc_ctr = float(row["gsc_ctr"]) if row["gsc_ctr"] is not None else None
        f.gsc_avg_position = float(row["gsc_avg_position"]) if row["gsc_avg_position"] is not None else None


async def _load_competitor_freshness_days(
    session: AsyncSession,
    facts: dict[UUID, ClusterFacts],
    now: datetime,
) -> None:
    # Median age of competitor (RSS) articles in the cluster.
    # Lower = competitors published recently, topic still hot.
    sql = text(
        """
        SELECT
            m.cluster_id,
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (
                    :now - COALESCE(a.published_at, a.created_at)
                )) / 86400
            )::int AS competitor_freshness_days
        FROM article_cluster_member m
        JOIN article a         ON a.id = m.article_id
        JOIN content_source cs ON cs.id = a.source_id AND cs.source_type = 'rss'
        JOIN article_cluster c ON c.id = m.cluster_id AND c.is_current = true
        WHERE NOT EXISTS (
            SELECT 1 FROM article_cluster child WHERE child.parent_cluster_id = c.id
        )
        GROUP BY m.cluster_id
        """
    )
    rows = (await session.execute(sql, {"now": now})).mappings()
    for row in rows:
        cid = row["cluster_id"]
        f = facts.setdefault(cid, ClusterFacts())
        val = row["competitor_freshness_days"]
        f.competitor_freshness_days = int(val) if val is not None else None


def _compute_quadrant(high_demand: bool, performance_level: str) -> str:
    if performance_level == "too_early":
        return "too_early"
    if high_demand:
        return "opportunity" if performance_level in ("none", "low") else "winning"
    return "evergreen" if performance_level == "high" else "ignore"


def _normalize_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(tzinfo=None)
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value
