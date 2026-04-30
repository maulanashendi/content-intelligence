from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CoverageInputs:
    competitor_articles: int
    internal_articles: int
    recent_internal_articles: int
    internal_underperformed: bool


def compute_coverage_score(inputs: CoverageInputs) -> float:
    total_articles = inputs.competitor_articles + inputs.internal_articles
    competitor_share = (
        inputs.competitor_articles / total_articles if total_articles > 0 else 0.0
    )

    if inputs.recent_internal_articles > 0:
        internal_gap = 0.0 if not inputs.internal_underperformed else 0.35
    elif inputs.internal_articles > 0:
        internal_gap = 0.55
    else:
        internal_gap = 1.0

    score = (competitor_share * 0.65) + (internal_gap * 0.35)
    return round(min(max(score, 0.0), 1.0), 4)
