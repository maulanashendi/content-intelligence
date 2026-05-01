from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer


def _serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        # Backend convention: naive timestamps are UTC. Tag them so the wire
        # format is unambiguous (`Z` suffix); the frontend then formats in
        # Asia/Jakarta without guessing.
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str)]
