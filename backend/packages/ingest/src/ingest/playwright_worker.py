import asyncio
import logging
import time
from collections import defaultdict
from urllib.parse import urlparse
from uuid import UUID

import trafilatura
from core.config import settings
from core.db import get_session
from core.models import Article, ScrapeStatus
from playwright.async_api import async_playwright
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EditorIntelligenceBot/1.0; +https://tempo.co)",
}
_DOMAIN_DELAY_SECONDS = 2.0
_MAX_PLAYWRIGHT_ATTEMPTS = 2


async def _scrape_batch(articles: list[tuple[UUID, str]]) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            domain_last: dict[str, float] = defaultdict(float)
            for article_id, url in articles:
                domain = urlparse(url).netloc
                wait = domain_last[domain] + _DOMAIN_DELAY_SECONDS - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)

                content = None
                try:
                    page = await browser.new_page()
                    await page.set_extra_http_headers(_HEADERS)
                    await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                    html = await page.content()
                    await page.close()
                    content = (
                        trafilatura.extract(html, include_comments=False, include_tables=False)
                        or None
                    )
                except Exception as exc:
                    logger.warning(
                        "playwright_page_error article_id=%s error=%s", article_id, exc
                    )

                domain_last[domain] = time.monotonic()

                async with get_session() as session:
                    current_attempts = (
                        await session.execute(
                            select(Article.scrape_attempts).where(Article.id == article_id)
                        )
                    ).scalar_one()

                if content:
                    status = ScrapeStatus.playwright_ok
                elif (current_attempts + 1) >= _MAX_PLAYWRIGHT_ATTEMPTS:
                    status = ScrapeStatus.playwright_failed
                else:
                    status = ScrapeStatus.fast_failed

                async with get_session() as session:
                    await session.execute(
                        update(Article)
                        .where(Article.id == article_id)
                        .values(
                            content=content,
                            scrape_status=status,
                            scrape_attempts=Article.scrape_attempts + 1,
                        )
                    )
                    await session.commit()

                logger.debug(
                    "playwright_done article_id=%s status=%s", article_id, status.value
                )
        finally:
            await browser.close()


async def run_loop(shutdown: asyncio.Event) -> None:
    while not shutdown.is_set():
        try:
            async with get_session() as session:
                rows = (
                    await session.execute(
                        select(Article.id, Article.url)
                        .where(Article.scrape_status == ScrapeStatus.fast_failed)
                        .limit(settings.playwright_batch_size)
                    )
                ).all()

            if rows:
                logger.info("playwright_batch_start count=%d", len(rows))
                await _scrape_batch([(r.id, r.url) for r in rows])
                logger.info("playwright_batch_finish count=%d", len(rows))
        except Exception as exc:
            logger.error("playwright_worker_error error=%s", exc)

        try:
            await asyncio.wait_for(
                asyncio.shield(shutdown.wait()),
                timeout=settings.playwright_poll_interval_seconds,
            )
        except asyncio.TimeoutError:
            pass
