import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from core.config import settings
from core.db import get_session
from core.models import Article, ContentSource, ScrapeStatus, SourceStatus, SourceType
from ingest.parser import parse_feed
from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

# WAFs (Cloudflare, RunCloud 7G, etc.) routinely block the default
# `python-httpx/x.y` UA, returning 403 or a redirect to a block page.
# Identify as a real-looking RSS reader so feeds answer normally.
DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (compatible; EditorIntelligenceBot/1.0; +https://tempo.co)"),
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "id, en;q=0.7",
}


def make_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.ingest_timeout_seconds),
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
    )


class BlockedError(Exception):
    pass


async def _set_source_status(source_id: UUID, status: SourceStatus) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    async with get_session() as session:
        await session.execute(
            update(ContentSource)
            .where(ContentSource.id == source_id)
            .values(status=status, last_fetched_at=now, updated_at=now)
        )
        await session.commit()
    logger.info("source_status_set source_id=%s status=%s", source_id, status.value)


async def fetch_and_store_source(
    client: httpx.AsyncClient,
    source_id: UUID,
    source_url: str,
    source_name: str,
) -> int:
    """Fetch one RSS source and persist articles + status atomically.

    Raises BlockedError on 403/429 so the caller can mark the source blocked
    in its own retention policy. Other exceptions propagate untouched.
    """
    resp = await client.get(source_url)
    if resp.status_code in (403, 429):
        raise BlockedError(f"source={source_name} http_status={resp.status_code}")
    resp.raise_for_status()
    entries, fmt = parse_feed(resp.content, source_name)

    now = datetime.now(UTC).replace(tzinfo=None)
    inserted = 0
    async with get_session() as session:
        for entry in entries:
            stmt = pg_insert(Article).values(
                source_id=source_id,
                title=entry["title"],
                url=entry["url"],
                published_at=entry.get("published_at"),
                first_paragraph=entry.get("first_paragraph"),
                scrape_status=ScrapeStatus.pending,
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
            result = await session.execute(stmt)
            inserted += result.rowcount or 0

        await session.execute(
            update(ContentSource)
            .where(ContentSource.id == source_id)
            .values(status=SourceStatus.active, last_fetched_at=now, updated_at=now)
        )
        await session.commit()
    logger.debug("rss source=%s format=%s entries=%d inserted=%d", source_name, fmt, len(entries), inserted)
    return inserted


async def _ingest_one(
    client: httpx.AsyncClient,
    source_id: UUID,
    source_url: str,
    source_name: str,
) -> int:
    try:
        count = await fetch_and_store_source(client, source_id, source_url, source_name)
    except BlockedError:
        logger.warning("source=%s blocked by provider", source_name)
        await _set_source_status(source_id, SourceStatus.blocked)
        return 0
    except Exception:
        logger.exception("failed to fetch source=%s url=%s", source_name, source_url)
        await _set_source_status(source_id, SourceStatus.error)
        return 0
    logger.info("rss source=%s entries=%d", source_name, count)
    return count


async def ingest_rss(client: httpx.AsyncClient) -> int:
    now = datetime.now(UTC).replace(tzinfo=None)
    error_cutoff = now - timedelta(seconds=settings.source_error_backoff_seconds)
    blocked_cutoff = now - timedelta(seconds=settings.source_blocked_backoff_seconds)

    async with get_session() as session:
        result = await session.execute(
            select(ContentSource.id, ContentSource.url, ContentSource.name).where(
                ContentSource.source_type == SourceType.rss,
                ContentSource.is_enabled.is_(True),
                or_(
                    ContentSource.status.is_(None),
                    ContentSource.status == SourceStatus.active,
                    and_(
                        ContentSource.status == SourceStatus.error,
                        or_(
                            ContentSource.last_fetched_at.is_(None),
                            ContentSource.last_fetched_at < error_cutoff,
                        ),
                    ),
                    and_(
                        ContentSource.status == SourceStatus.blocked,
                        or_(
                            ContentSource.last_fetched_at.is_(None),
                            ContentSource.last_fetched_at < blocked_cutoff,
                        ),
                    ),
                ),
            )
        )
        sources = result.all()

    if not sources:
        logger.warning("no enabled RSS sources found")
        return 0

    counts = await asyncio.gather(
        *[_ingest_one(client, sid, surl, sname) for sid, surl, sname in sources]
    )
    return sum(counts)
