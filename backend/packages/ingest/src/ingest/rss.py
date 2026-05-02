import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from uuid import UUID

import feedparser
import httpx
from core.config import settings
from core.db import get_session
from core.models import Article, ContentSource, SourceStatus, SourceType
from lxml import html as lxml_html
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

# WAFs (Cloudflare, RunCloud 7G, etc.) routinely block the default
# `python-httpx/x.y` UA, returning 403 or a redirect to a block page.
# Identify as a real-looking RSS reader so feeds answer normally.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EditorIntelligenceBot/1.0; "
        "+https://tempo.co)"
    ),
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


def _html_to_text(raw: str) -> str:
    if not raw:
        return ""
    try:
        return lxml_html.fromstring(raw).text_content().strip()
    except Exception:
        return raw.strip()


def _parse_entry(entry: feedparser.FeedParserDict) -> dict:
    title = entry.get("title", "").strip()
    link = entry.get("link", "").strip()
    if not title or not link:
        return {}

    published_at = None
    for attr in ("published_parsed", "updated_parsed"):
        time_struct = entry.get(attr)
        if time_struct:
            with contextlib.suppress(TypeError, ValueError):
                published_at = datetime(*time_struct[:6])
                break

    summary = entry.get("summary", "").strip()

    first_paragraph = None
    if summary:
        first_paragraph = _html_to_text(summary)[:2000] or None

    return {
        "title": title,
        "url": link,
        "published_at": published_at,
        "first_paragraph": first_paragraph,
    }


async def _set_source_status(source_id: UUID, status: SourceStatus) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    async with get_session() as session:
        await session.execute(
            update(ContentSource)
            .where(ContentSource.id == source_id)
            .values(status=status, updated_at=now)
        )
        await session.commit()


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
    feed = feedparser.parse(resp.text)

    now = datetime.now(UTC).replace(tzinfo=None)
    inserted = 0
    async with get_session() as session:
        for entry in feed.entries:
            parsed = _parse_entry(entry)
            if not parsed:
                continue
            stmt = pg_insert(Article).values(source_id=source_id, **parsed)
            stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
            result = await session.execute(stmt)
            inserted += result.rowcount or 0

        await session.execute(
            update(ContentSource)
            .where(ContentSource.id == source_id)
            .values(status=SourceStatus.active, last_fetched_at=now, updated_at=now)
        )
        await session.commit()
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
    async with get_session() as session:
        result = await session.execute(
            select(ContentSource.id, ContentSource.url, ContentSource.name).where(
                ContentSource.source_type == SourceType.rss,
                ContentSource.is_enabled.is_(True),
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
