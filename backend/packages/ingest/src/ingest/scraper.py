import asyncio
import logging
from uuid import UUID

import httpx
import trafilatura
from core.config import settings
from core.db import get_session
from core.models import Article, ScrapeStatus
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EditorIntelligenceBot/1.0; +https://tempo.co)",
    "Accept-Language": "id, en;q=0.7",
}


async def _fetch_and_extract(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            timeout=settings.scrape_fast_timeout_seconds,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
        return text or None
    except Exception:
        return None


async def run() -> None:
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Article.id, Article.url).where(
                    Article.scrape_status == ScrapeStatus.pending
                )
            )
        ).all()

    if not rows:
        return

    logger.info("scrape_fast_start count=%d", len(rows))

    sem = asyncio.Semaphore(10)

    async def _scrape_one(article_id: UUID, url: str) -> None:
        async with sem:
            content = await _fetch_and_extract(url)
        status = ScrapeStatus.fast_ok if content else ScrapeStatus.fast_failed
        async with get_session() as session:
            await session.execute(
                update(Article)
                .where(Article.id == article_id)
                .values(content=content, scrape_status=status)
            )
            await session.commit()
        logger.debug("scrape_fast_done article_id=%s status=%s", article_id, status.value)

    await asyncio.gather(*[_scrape_one(r.id, r.url) for r in rows])
    logger.info("scrape_fast_finish count=%d", len(rows))
