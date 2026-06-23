"""Fetch Google Search Console data and upsert into gsc_page, gsc_query, gsc_page_query."""

import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.config import Settings, settings as default_settings
from core.models import Article, ArticleGscMetric, ContentSource, GscPage, GscPageQuery, GscQuery, SourceType
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
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


_NORM_SCHEME = re.compile(r"^https?://")
_NORM_PREFIX = re.compile(r"^(www\.|en\.|m\.)")
_NORM_SUFFIX = re.compile(r"[?#].*$")
# Trailing numeric ID in Tempo slugs: ...-<6+digits> at path end
_TEMPO_ID_TRAIL = re.compile(r"-(\d{6,})/?$")
# en.tempo.co /read/<id>/ format
_TEMPO_ID_READ = re.compile(r"/read/(\d{5,})/")


def _normalize_url(url: str) -> str:
    url = url.lower()
    url = _NORM_SCHEME.sub("", url)
    url = _NORM_PREFIX.sub("", url)
    url = _NORM_SUFFIX.sub("", url)
    return url.rstrip("/")


def _extract_id_suffix(url: str) -> str | None:
    m = _TEMPO_ID_TRAIL.search(url)
    if m:
        return m.group(1)
    m = _TEMPO_ID_READ.search(url)
    if m:
        return m.group(1)
    return None


async def link_articles(session: AsyncSession, gsc_fetch_days: int | None = None) -> int:
    """Map gsc_page rows to internal articles and upsert into article_gsc_metric.

    Matching strategy (in order):
    1. Exact normalized URL (strip scheme / www|en|m / query / trailing slash).
    2. Trailing numeric ID fallback — Tempo slugs end in -<digits>; en.tempo.co
       uses /read/<id>/ — used when exact norm fails.

    Aggregates impression-weighted avg_position and sums clicks/impressions when
    multiple gsc_page rows map to the same (article, period) — rare in practice.
    """
    window_days = gsc_fetch_days if gsc_fetch_days is not None else default_settings.gsc_fetch_days
    cutoff = date.today() - timedelta(days=window_days)

    # Load internal articles
    rows = (
        await session.execute(
            select(Article.id, Article.url)
            .join(ContentSource, ContentSource.id == Article.source_id)
            .where(ContentSource.source_type == SourceType.internal)
        )
    ).all()

    norm_to_id: dict[str, uuid.UUID] = {}
    suffix_to_id: dict[str, uuid.UUID] = {}
    for art_id, url in rows:
        norm = _normalize_url(url)
        norm_to_id[norm] = art_id
        suffix = _extract_id_suffix(url)
        # First article found for a given suffix wins; avoids false cross-matches
        if suffix and suffix not in suffix_to_id:
            suffix_to_id[suffix] = art_id

    if not norm_to_id:
        logger.info("gsc link_articles: no internal articles found, skipping")
        return 0

    # Load gsc_page rows whose window ends within the configured fetch horizon.
    # Filter by period_end (not period_start) so a multi-day window like
    # 2026-05-01→2026-06-01 is included as long as its end date is recent enough.
    gsc_rows = (
        await session.execute(
            select(
                GscPage.page_url,
                GscPage.clicks,
                GscPage.impressions,
                GscPage.avg_position,
                GscPage.period_start,
                GscPage.period_end,
            ).where(GscPage.period_end >= cutoff)
        )
    ).all()

    # Match and aggregate per (article_id, period_start, period_end)
    # value: {clicks, impressions, weighted_pos_num, weighted_pos_den}
    agg: dict[tuple[uuid.UUID, date, date], dict] = {}
    matched_exact = 0
    matched_id = 0
    unmatched = 0

    for page_url, clicks, impressions, avg_position, period_start, period_end in gsc_rows:
        article_id = norm_to_id.get(_normalize_url(page_url))
        if article_id is not None:
            matched_exact += 1
        else:
            suffix = _extract_id_suffix(page_url)
            article_id = suffix_to_id.get(suffix) if suffix else None
            if article_id is not None:
                matched_id += 1
            else:
                unmatched += 1
                continue

        key = (article_id, period_start, period_end)
        if key not in agg:
            agg[key] = {"clicks": 0, "impressions": 0, "wpos_num": 0.0, "wpos_den": 0}
        bucket = agg[key]
        bucket["clicks"] += clicks or 0
        imp = impressions or 0
        bucket["impressions"] += imp
        if avg_position is not None and imp > 0:
            bucket["wpos_num"] += avg_position * imp
            bucket["wpos_den"] += imp

    logger.info(
        "gsc link_articles: matched exact=%d id_fallback=%d unmatched=%d",
        matched_exact,
        matched_id,
        unmatched,
    )

    if not agg:
        return 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    values = []
    for (article_id, period_start, period_end), bucket in agg.items():
        imp = bucket["impressions"]
        clk = bucket["clicks"]
        avg_pos = (bucket["wpos_num"] / bucket["wpos_den"]) if bucket["wpos_den"] > 0 else None
        ctr_val = (clk / imp) if imp > 0 else None
        values.append(
            {
                "article_id": article_id,
                "clicks": clk,
                "impressions": imp,
                "ctr": ctr_val,
                "avg_position": avg_pos,
                "period_start": period_start,
                "period_end": period_end,
                "fetched_at": now,
            }
        )

    for batch in _chunked(values, _BATCH_SIZE):
        stmt = pg_insert(ArticleGscMetric).values(batch)
        await session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_gsc_metric_article_period",
                set_={
                    "clicks": stmt.excluded.clicks,
                    "impressions": stmt.excluded.impressions,
                    "ctr": stmt.excluded.ctr,
                    "avg_position": stmt.excluded.avg_position,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
        )
    await session.commit()

    logger.info("gsc link_articles: upserted %d article_gsc_metric rows", len(values))
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
