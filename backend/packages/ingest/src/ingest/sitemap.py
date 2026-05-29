import logging
from datetime import UTC, datetime

import httpx
from core.db import get_session
from core.models import Article, ContentSource, ScrapeStatus, SourceStatus, SourceType
from ingest.parser import parse_feed
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)


async def ingest_sitemap(client: httpx.AsyncClient) -> int:
    async with get_session() as session:
        result = await session.execute(
            select(ContentSource).where(
                ContentSource.source_type == SourceType.internal,
                ContentSource.is_enabled.is_(True),
            )
        )
        sources = list(result.scalars().all())
        if not sources:
            logger.warning("no enabled sitemap sources found")
            return 0

        total_inserted = 0
        now = datetime.now(UTC).replace(tzinfo=None)

        for source in sources:
            try:
                resp = await client.get(source.url)
                resp.raise_for_status()
            except Exception:
                logger.exception(
                    "failed to fetch sitemap source=%s url=%s", source.name, source.url
                )
                source.status = SourceStatus.error
                source.updated_at = now
                continue

            entries, fmt = parse_feed(resp.content, source.name)
            inserted = 0

            for entry in entries:
                stmt = pg_insert(Article).values(
                    source_id=source.id,
                    title=entry["title"],
                    url=entry["url"],
                    published_at=entry.get("published_at"),
                    first_paragraph=entry.get("first_paragraph"),
                    scrape_status=ScrapeStatus.pending,
                )
                stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
                result = await session.execute(stmt)
                inserted += result.rowcount or 0

            source.status = SourceStatus.active
            source.last_fetched_at = now
            source.updated_at = now
            total_inserted += inserted
            logger.info("internal source=%s format=%s entries=%d", source.name, fmt, inserted)

        await session.commit()
        return total_inserted
