from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

NOVELTY_WINDOW_DAYS = 30


def compute_novelty_score(
    published_at_values: Sequence[datetime | None],
    *,
    now: datetime | None = None,
) -> float:
    timestamps = [published_at for published_at in published_at_values if published_at is not None]
    if not timestamps:
        return 0.0

    current_time = _normalize_now(now)
    earliest = min(_normalize_timestamp(published_at) for published_at in timestamps)
    age_days = max((current_time - earliest).total_seconds() / 86400, 0.0)

    if age_days >= NOVELTY_WINDOW_DAYS:
        return 0.0

    return round(1.0 - (age_days / NOVELTY_WINDOW_DAYS), 4)


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC).replace(tzinfo=None)
    return _normalize_timestamp(now)


def _normalize_timestamp(timestamp: datetime) -> datetime:
    return (
        timestamp.astimezone(UTC).replace(tzinfo=None)
        if timestamp.tzinfo is not None
        else timestamp
    )
