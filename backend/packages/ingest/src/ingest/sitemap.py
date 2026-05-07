import contextlib
import logging
from datetime import UTC, datetime

import httpx
from core.db import get_session
from core.models import Article, ContentSource, ScrapeStatus, SourceStatus, SourceType
from lxml import etree
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)


async def _fetch_sitemap_xml(client: httpx.AsyncClient, source: ContentSource) -> bytes:
    resp = await client.get(source.url)
    resp.raise_for_status()
    return resp.content


def _parse_sitemap(xml_bytes: bytes) -> list[dict]:
    tree = etree.fromstring(xml_bytes)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    entries = []

    for url_el in tree.findall("sm:url", ns):
        loc = url_el.find("sm:loc", ns)
        if loc is None or not (loc.text or "").strip():
            continue

        lastmod = url_el.find("sm:lastmod", ns)
        published_at = None
        if lastmod is not None and (lastmod.text or "").strip():
            with contextlib.suppress(ValueError, TypeError):
                published_at = datetime.fromisoformat(lastmod.text.strip().rstrip("Z"))

        entries.append(
            {
                "url": loc.text.strip(),
                "published_at": published_at,
            }
        )

    return entries


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
                xml_bytes = await _fetch_sitemap_xml(client, source)
            except Exception:
                logger.exception(
                    "failed to fetch sitemap source=%s url=%s", source.name, source.url
                )
                source.status = SourceStatus.error
                source.updated_at = now
                continue

            entries = _parse_sitemap(xml_bytes)
            inserted = 0

            for entry in entries:
                title = entry["url"].rstrip("/").split("/")[-1].replace("-", " ").title()
                if not title:
                    continue

                stmt = pg_insert(Article).values(
                    source_id=source.id,
                    title=title,
                    url=entry["url"],
                    published_at=entry["published_at"],
                    scrape_status=ScrapeStatus.pending,
                )
                stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
                await session.execute(stmt)
                inserted += 1

            source.status = SourceStatus.active
            source.last_fetched_at = now
            source.updated_at = now
            total_inserted += inserted
            logger.info("sitemap source=%s entries=%d", source.name, inserted)

        await session.commit()
        return total_inserted
