from datetime import datetime, timedelta, timezone
from typing import Literal

from api.types import UtcDateTime
from pydantic import BaseModel

_WIB = timezone(timedelta(hours=7))
_RANGE: dict[str, tuple[timedelta, int]] = {
    "hour": (timedelta(hours=1), 48),
    "day": (timedelta(days=1), 30),
}


class VolumeBucket(BaseModel):
    bucket_start: UtcDateTime
    competitor_count: int
    internal_count: int
    competitor_avg_per_source: float


class VolumeTrendResponse(BaseModel):
    bucket: Literal["hour", "day"]
    buckets: list[VolumeBucket]
    generated_at: UtcDateTime


def dense_bucket_starts(bucket: Literal["hour", "day"], now_utc: datetime) -> list[datetime]:
    """Naive WIB wall-clock bucket starts, oldest→newest, covering the range."""
    step, count = _RANGE[bucket]
    now_wib = now_utc.astimezone(_WIB).replace(tzinfo=None)
    if bucket == "hour":
        current = now_wib.replace(minute=0, second=0, microsecond=0)
    else:
        current = now_wib.replace(hour=0, minute=0, second=0, microsecond=0)
    return [current - step * i for i in range(count - 1, -1, -1)]
