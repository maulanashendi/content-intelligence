"""
Benchmark: single-call cluster insight via production generate_cluster_insight.

Selects 10 clusters spanning the size distribution, runs the full production
labeling pipeline (sub-cluster → MMR representatives → one Gemma call), and
reports fill rates and timing.

Read-only — fetches from DB but does not write.

Before (per-article LLM calls):
  ~1,610 calls × 55s avg = ~27h

After (one call per cluster):
  ~230 calls × 60s avg = ~4h (conservative; actual ~60-90 min on CPU)

Run:
    docker exec content-intelligence-pipeline-daemon-1 \
        python /app/scripts/benchmark_single_call_insight.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid

import numpy as np
from core.db import get_session
from core.models import Article, ArticleCluster, ArticleClusterMember, ArticleEmbedding
from labeling.llm import generate_cluster_insight, get_llm
from labeling.pipeline import _get_representative_articles, _get_top_articles
from sqlalchemy import select

logger = logging.getLogger("benchmark")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

PER_ARTICLE_BASELINE_SECONDS = 55.4


async def fetch_clusters_spanning_sizes() -> list[tuple[uuid.UUID, str | None, int]]:
    async with get_session() as session:
        rows = (
            await session.execute(
                select(ArticleCluster.id, ArticleCluster.label, ArticleCluster.member_count)
                .where(ArticleCluster.is_current.is_(True))
                .order_by(ArticleCluster.member_count.asc())
            )
        ).all()

    valid = [r for r in rows if (r.member_count or 0) >= 3]
    if not valid:
        return []
    idxs = np.linspace(0, len(valid) - 1, num=min(10, len(valid)), dtype=int)
    return [(valid[i].id, valid[i].label, valid[i].member_count) for i in idxs]


def warmup() -> None:
    logger.info("warming up Gemma")
    get_llm()
    logger.info("warmup complete")


async def run_one(cluster_id: uuid.UUID, label: str | None, size: int) -> dict:
    async with get_session() as session:
        reps = await _get_representative_articles(session, cluster_id)
        if not reps:
            reps = await _get_top_articles(session, cluster_id)

    if not reps:
        return {
            "cluster_id": str(cluster_id),
            "label": label,
            "size": size,
            "reps": 0,
            "seconds": 0.0,
            "label_filled": False,
            "what_happened_filled": False,
            "editorial_angle_filled": False,
            "parties_count": 0,
            "summary_count": 0,
            "error": "no_articles",
        }

    t0 = time.perf_counter()
    try:
        result = await generate_cluster_insight(reps)
        elapsed = time.perf_counter() - t0
        return {
            "cluster_id": str(cluster_id),
            "label": label,
            "size": size,
            "reps": len(reps),
            "seconds": round(elapsed, 2),
            "label_filled": bool(result.get("label")),
            "what_happened_filled": bool(result.get("what_happened")),
            "editorial_angle_filled": bool(result.get("editorial_angle")),
            "parties_count": len(result.get("parties_involved") or []),
            "summary_count": len(result.get("summary") or []),
            "result": result,
        }
    except Exception as exc:
        return {
            "cluster_id": str(cluster_id),
            "label": label,
            "size": size,
            "reps": len(reps),
            "seconds": round(time.perf_counter() - t0, 2),
            "error": str(exc),
        }


def print_report(results: list[dict]) -> None:
    ok = [r for r in results if "error" not in r]
    err = [r for r in results if "error" in r]

    print()
    print("=" * 100)
    print(f"SINGLE-CALL INSIGHT BENCHMARK  (sampled {len(results)} clusters)")
    print("=" * 100)
    headers = ("size", "reps", "time(s)", "old(s)*", "label", "what_happened", "angle", "parties", "claims", "cluster-label")
    rows: list[tuple[str, ...]] = [headers]
    total_new = 0.0
    total_old = 0.0
    for r in ok:
        old = r["size"] * PER_ARTICLE_BASELINE_SECONDS
        total_new += r["seconds"]
        total_old += old
        rows.append((
            str(r["size"]),
            str(r["reps"]),
            f"{r['seconds']:.1f}",
            f"{old:.0f}",
            "✓" if r["label_filled"] else "✗",
            "✓" if r["what_happened_filled"] else "✗",
            "✓" if r["editorial_angle_filled"] else "✗",
            str(r["parties_count"]),
            str(r["summary_count"]),
            (r["label"] or "(none)")[:40],
        ))
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    for row in rows:
        print("  ".join(c.ljust(widths[i]) for i, c in enumerate(row)))

    if err:
        print(f"\nErrors ({len(err)}):")
        for r in err:
            print(f"  cluster={r['cluster_id'][:8]}  error={r['error']}")

    if ok:
        label_rate = sum(1 for r in ok if r["label_filled"]) / len(ok)
        angle_rate = sum(1 for r in ok if r["editorial_angle_filled"]) / len(ok)
        print(f"\nFill rates: label={label_rate:.0%}  editorial_angle={angle_rate:.0%}")
        print(f"Total time (new, sample): {total_new:.1f}s")
        print(f"Total time (old, estimated): {total_old:.0f}s")
        if total_new > 0:
            print(f"Sample speedup: {total_old / total_new:.1f}x")

    print()
    print("=" * 100)
    print("QUALITY SAMPLE")
    print("=" * 100)
    for r in ok:
        res = r.get("result", {})
        print(f"\n[{r['cluster_id'][:8]}] size={r['size']} reps={r['reps']} time={r['seconds']:.1f}s")
        print(f"  label        : {res.get('label')!r}")
        print(f"  what_happened: {(res.get('what_happened') or '')[:100]!r}")
        print(f"  editorial_angle: {res.get('editorial_angle')!r}")
        for p in (res.get("parties_involved") or [])[:3]:
            print(f"  PIHAK  : {p}")
        for c in (res.get("summary") or [])[:3]:
            print(f"  KLAIM  : {c}")


async def main() -> int:
    logger.info("fetching clusters spanning size distribution")
    clusters = await fetch_clusters_spanning_sizes()
    if not clusters:
        logger.error("no clusters found")
        return 1
    logger.info("selected %d clusters", len(clusters))

    warmup()

    results: list[dict] = []
    for cluster_id, label, size in clusters:
        logger.info("running cluster size=%d label=%r", size, label)
        results.append(await run_one(cluster_id, label, size))

    print_report(results)
    print()
    print("JSON_SUMMARY:", json.dumps([
        {k: v for k, v in r.items() if k not in ("result",)}
        for r in results
    ]))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
