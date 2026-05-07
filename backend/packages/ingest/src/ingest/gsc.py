"""Fetch Google Search Console data and upsert into gsc_page, gsc_query, gsc_page_query."""

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.config import Settings
from core.models import GscPage, GscPageQuery, GscQuery
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
_ROW_LIMIT = 5000
# asyncpg hard limit is 32767 params per query; batch conservatively
_BATCH_SIZE = 500


def _chunked(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def _resolve_credentials(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def _build_service(credentials_path: Path):
    creds = service_account.Credentials.from_service_account_file(
        str(credentials_path), scopes=_SCOPES
    )
    return build("searchconsole", "v1", credentials=creds)


def _date_range(fetch_days: int) -> tuple[str, str]:
    end = date.today() - timedelta(days=1)  # GSC lags ~1 day
    start = end - timedelta(days=fetch_days - 1)
    return start.isoformat(), end.isoformat()


def _fetch_rows(service, site_url: str, start: str, end: str, dimensions: list[str]) -> list[dict]:
    body = {"startDate": start, "endDate": end, "dimensions": dimensions, "rowLimit": _ROW_LIMIT}
    try:
        response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        return response.get("rows", [])
    except HttpError as exc:
        label = "+".join(dimensions)
        logger.warning("GSC API error dim=%s status=%s reason=%s", label, exc.status_code, exc.reason)
        return []


async def _upsert_pages(
    session: AsyncSession, rows: list[dict], period_start: date, period_end: date
) -> int:
    if not rows:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    values = [
        {
            "page_url": r["keys"][0],
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": r.get("ctr"),
            "avg_position": r.get("position"),
            "period_start": period_start,
            "period_end": period_end,
            "fetched_at": now,
        }
        for r in rows
        if r.get("keys")
    ]
    for batch in _chunked(values, _BATCH_SIZE):
        stmt = pg_insert(GscPage).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_gsc_page_url_period",
            set_={
                "clicks": stmt.excluded.clicks,
                "impressions": stmt.excluded.impressions,
                "ctr": stmt.excluded.ctr,
                "avg_position": stmt.excluded.avg_position,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await session.execute(stmt)
    return len(values)


async def _upsert_queries(
    session: AsyncSession, rows: list[dict], period_start: date, period_end: date
) -> int:
    if not rows:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    values = [
        {
            "query": r["keys"][0],
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": r.get("ctr"),
            "avg_position": r.get("position"),
            "period_start": period_start,
            "period_end": period_end,
            "fetched_at": now,
        }
        for r in rows
        if r.get("keys")
    ]
    for batch in _chunked(values, _BATCH_SIZE):
        stmt = pg_insert(GscQuery).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_gsc_query_period",
            set_={
                "clicks": stmt.excluded.clicks,
                "impressions": stmt.excluded.impressions,
                "ctr": stmt.excluded.ctr,
                "avg_position": stmt.excluded.avg_position,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await session.execute(stmt)
    return len(values)


async def _upsert_page_queries(
    session: AsyncSession, rows: list[dict], period_start: date, period_end: date
) -> int:
    if not rows:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    values = [
        {
            "page_url": r["keys"][0],
            "query": r["keys"][1],
            "clicks": int(r.get("clicks", 0)),
            "impressions": int(r.get("impressions", 0)),
            "ctr": r.get("ctr"),
            "avg_position": r.get("position"),
            "period_start": period_start,
            "period_end": period_end,
            "fetched_at": now,
        }
        for r in rows
        if len(r.get("keys", [])) >= 2
    ]
    for batch in _chunked(values, _BATCH_SIZE):
        stmt = pg_insert(GscPageQuery).values(batch)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_gsc_page_query_period",
            set_={
                "clicks": stmt.excluded.clicks,
                "impressions": stmt.excluded.impressions,
                "ctr": stmt.excluded.ctr,
                "avg_position": stmt.excluded.avg_position,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await session.execute(stmt)
    return len(values)


async def run(session: AsyncSession, settings: Settings) -> None:
    credentials_path = _resolve_credentials(settings.gsc_credentials_path)
    if not credentials_path.exists():
        logger.warning("GSC credentials not found at %s, skipping fetch", credentials_path)
        return

    try:
        service = _build_service(credentials_path)
    except Exception:
        logger.warning("Failed to build GSC service, skipping fetch", exc_info=True)
        return

    start_str, end_str = _date_range(settings.gsc_fetch_days)
    period_start = date.fromisoformat(start_str)
    period_end = date.fromisoformat(end_str)
    site_url = settings.gsc_site_url

    logger.info("GSC fetch start site=%s period=%s/%s", site_url, start_str, end_str)

    page_rows = _fetch_rows(service, site_url, start_str, end_str, ["page"])
    query_rows = _fetch_rows(service, site_url, start_str, end_str, ["query"])
    page_query_rows = _fetch_rows(service, site_url, start_str, end_str, ["page", "query"])

    n_pages = await _upsert_pages(session, page_rows, period_start, period_end)
    n_queries = await _upsert_queries(session, query_rows, period_start, period_end)
    n_page_queries = await _upsert_page_queries(session, page_query_rows, period_start, period_end)
    await session.commit()

    logger.info(
        "GSC fetch done pages=%d queries=%d page_queries=%d",
        n_pages,
        n_queries,
        n_page_queries,
    )
