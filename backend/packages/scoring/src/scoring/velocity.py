from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

RECENCY_WINDOW_DAYS = 7


def compute_trend_velocity(
    published_at_values: Sequence[datetime | None],
    interest_scores: Sequence[float | None],
    *,
    now: datetime | None = None,
) -> float:
    current_time = _normalize_now(now)
    recent_points = [
        _recency_weight(published_at, current_time)
        for published_at in published_at_values
        if published_at is not None
    ]
    article_signal = min(sum(recent_points) / 3.0, 1.0)

    normalized_interest = [
        min(max(score, 0.0), 100.0) / 100.0 for score in interest_scores if score is not None
    ]
    trend_signal = sum(normalized_interest) / len(normalized_interest) if normalized_interest else 0.0

    return round((article_signal * 0.6) + (trend_signal * 0.4), 4)


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC).replace(tzinfo=None)
    return now.astimezone(UTC).replace(tzinfo=None) if now.tzinfo is not None else now


def _recency_weight(published_at: datetime, now: datetime) -> float:
    normalized = published_at.astimezone(UTC).replace(tzinfo=None) if published_at.tzinfo else published_at
    age_days = max((now - normalized).total_seconds() / 86400, 0.0)
    if age_days >= RECENCY_WINDOW_DAYS:
        return 0.0
    return 1.0 - (age_days / RECENCY_WINDOW_DAYS)
