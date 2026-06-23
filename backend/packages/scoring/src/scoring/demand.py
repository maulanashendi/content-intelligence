from __future__ import annotations

from uuid import UUID

from scoring.velocity import compute_trend_velocity


def classify_demand(
    facts: dict,
    high_percentile: float,
) -> None:
    """Compute demand_score and high_demand for every ClusterFacts entry in-place.

    demand_score is a weighted combination of three normalised signals:
      - trend_match_count (distinct trending keywords, 40%)
      - weighted_trend_score (sum of keyword peak interest, 30%)
      - trend_velocity (count_24h / count_7d ratio, 30%)

    Each signal is min-max normalised across all clusters in the current run so
    differences in raw scale don't dominate. high_demand is True for clusters
    whose demand_score is >= the high_percentile rank AND score > 0 (clusters with
    zero external signal are never classified as high-demand regardless of cutoff).
    """
    if not facts:
        return

    cluster_ids = list(facts.keys())

    trend_match = [float(facts[cid].trend_match_count) for cid in cluster_ids]
    wts = [float(facts[cid].weighted_trend_score) for cid in cluster_ids]
    velocity = [
        compute_trend_velocity(facts[cid].count_24h, facts[cid].count_7d)
        for cid in cluster_ids
    ]

    tm_norm = _minmax(trend_match)
    wts_norm = _minmax(wts)
    vel_norm = _minmax(velocity)

    scores = [
        round(0.4 * tm + 0.3 * w + 0.3 * v, 4)
        for tm, w, v in zip(tm_norm, wts_norm, vel_norm)
    ]

    for cid, score in zip(cluster_ids, scores):
        facts[cid].demand_score = score

    cutoff = _percentile_cutoff(scores, high_percentile)
    for cid, score in zip(cluster_ids, scores):
        facts[cid].high_demand = score > 0.0 and score >= cutoff


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    mn, mx = min(values), max(values)
    span = mx - mn
    if span == 0.0:
        # All equal: nonzero signal → treat as full score; zero signal → no score.
        fill = 1.0 if mn > 0.0 else 0.0
        return [fill] * len(values)
    return [(v - mn) / span for v in values]


def _percentile_cutoff(values: list[float], p: float) -> float:
    """Value at the p-th rank boundary in sorted values.

    Uses round() so that with small n the top (1-p) fraction stays close to
    the configured percentage — e.g. p=0.66 with n=3 gives top 1 cluster (33%).
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = min(round(p * len(sorted_vals)), len(sorted_vals) - 1)
    return sorted_vals[idx]
