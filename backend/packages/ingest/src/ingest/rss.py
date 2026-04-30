import asyncio
import contextlib
import logging
from datetime import UTC, datetime

import feedparser
import httpx
from core.db import get_session
from core.models import Article, ContentSource, SourceStatus, SourceType
from lxml import html as lxml_html
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)


async def _fetch_feed(
    client: httpx.AsyncClient, source: ContentSource
) -> feedparser.FeedParserDict:
    resp = await client.get(source.url)
    resp.raise_for_status()
    return feedparser.parse(resp.text)


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


async def ingest_rss(client: httpx.AsyncClient) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(ContentSource).where(
                ContentSource.source_type == SourceType.rss,
                ContentSource.is_enabled.is_(True),
            )
        )
        sources = list(result.scalars().all())
        if not sources:
            logger.warning("no enabled RSS sources found")
            return 0

        now = datetime.now(UTC).replace(tzinfo=None)

        results = await asyncio.gather(
            *[_fetch_feed(client, s) for s in sources], return_exceptions=True
        )

        total_inserted = 0
        for source, feed_or_exc in zip(sources, results, strict=True):
            if isinstance(feed_or_exc, Exception):
                logger.exception(
                    "failed to fetch source=%s url=%s", source.name, source.url
                )
                source.status = SourceStatus.error
                source.updated_at = now
                continue

            inserted = 0
            for entry in feed_or_exc.entries:
                parsed = _parse_entry(entry)
                if not parsed:
                    continue

                stmt = pg_insert(Article).values(
                    source_id=source.id,
                    title=parsed["title"],
                    url=parsed["url"],
                    published_at=parsed["published_at"],
                    first_paragraph=parsed["first_paragraph"],
                )
                stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
                await session.execute(stmt)
                inserted += 1

            source.status = SourceStatus.active
            source.last_fetched_at = now
            source.updated_at = now
            total_inserted += inserted
            logger.info("rss source=%s entries=%d", source.name, inserted)

        await session.commit()
        return total_inserted
