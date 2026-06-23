from __future__ import annotations

_LEVEL_NONE = "none"
_LEVEL_TOO_EARLY = "too_early"
_LEVEL_LOW = "low"
_LEVEL_HIGH = "high"


def classify_performance(
    facts: dict,
    high_percentile: float,
) -> None:
    """Set performance_level on every ClusterFacts entry in-place.

    Levels:
      none       — cluster has no internal (Tempo) article at all.
      too_early  — covered by Tempo but no GSC data yet (article too new or
                   search volume not yet captured by the weekly GSC fetch).
      high       — covered, has GSC data, impressions >= run percentile cutoff,
                   and NOT in the underperformed state.
      low        — covered with GSC data but below the impression threshold or
                   flagged as underperformed.

    The impression cutoff is computed as the high_percentile rank among all
    covered clusters that have at least one impression, keeping the threshold
    relative to each daily run rather than a fixed absolute number.
    """
    if not facts:
        return

    covered_impressions = [
        float(f.gsc_impressions)
        for f in facts.values()
        if f.tempo_covered and f.gsc_impressions > 0
    ]

    if covered_impressions:
        sorted_imp = sorted(covered_impressions)
        idx = min(round(high_percentile * len(sorted_imp)), len(sorted_imp) - 1)
        impression_cutoff = sorted_imp[idx]
    else:
        impression_cutoff = 0.0

    for f in facts.values():
        if not f.tempo_covered:
            f.performance_level = _LEVEL_NONE
        elif f.gsc_impressions == 0:
            f.performance_level = _LEVEL_TOO_EARLY
        elif f.underperformed:
            f.performance_level = _LEVEL_LOW
        elif impression_cutoff > 0 and f.gsc_impressions >= impression_cutoff:
            f.performance_level = _LEVEL_HIGH
        else:
            f.performance_level = _LEVEL_LOW
