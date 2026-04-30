import logging
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import feedparser
import httpx
from core.db import get_session
from core.models import (
    Article,
    ContentSource,
    TrendSignal,
    TrendSignalArticle,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=ID"


def _extract_traffic_number(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"([\d.]+)\s*[KkMmBb]?", text.replace(",", ""))
    if not match:
        return None
    raw = match.group(1)
    multiplier = 1.0
    if "K" in text.upper():
        multiplier = 1_000.0
    elif "M" in text.upper():
        multiplier = 1_000_000.0
    try:
        return float(raw) * multiplier
    except ValueError:
        return None


def _parse_trends_feed(feed: feedparser.FeedParserDict, now: datetime) -> list[dict]:
    trends = []
    for entry in feed.entries:
        keyword = entry.get("title", "").strip()
        if not keyword:
            continue

        interest_score = _extract_traffic_number(entry.get("ht:approx_traffic"))

        related_urls = []
        for link_el in entry.get("ht:news_item", []):
            news_url = link_el.get("ht:news_item_url", "").strip()
            news_title = link_el.get("ht:news_item_title", "").strip()
            if news_url and news_title:
                related_urls.append({"title": news_title, "url": news_url})

        trends.append(
            {
                "keyword": keyword,
                "interest_score": interest_score,
                "captured_at": now,
                "articles": related_urls,
            }
        )

    return trends


async def _resolve_source(session: AsyncSession, article_url: str) -> uuid.UUID | None:
    host = urlparse(article_url).hostname or ""
    result = await session.execute(
        select(ContentSource).where(ContentSource.url.ilike(f"%{host}%"))
    )
    source = result.scalar_one_or_none()
    return source.id if source else None


async def ingest_trends(client: httpx.AsyncClient) -> int:
    try:
        resp = await client.get(TRENDS_RSS_URL)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception:
        logger.exception("failed to fetch Google Trends RSS")
        return 0

    now = datetime.now(UTC).replace(tzinfo=None)
    parsed_trends = _parse_trends_feed(feed, now)
    if not parsed_trends:
        logger.info("trends: no trending topics found")
        return 0

    total_signals = 0

    async with get_session() as session:
        for trend in parsed_trends:
            async with session.begin():
                signal_stmt = pg_insert(TrendSignal).values(
                    keyword=trend["keyword"],
                    interest_score=trend["interest_score"],
                    captured_at=trend["captured_at"],
                )
                signal_stmt = signal_stmt.on_conflict_do_nothing(
                    constraint="uq_trend_signal_keyword_captured_at"
                )
                await session.execute(signal_stmt)

                result = await session.execute(
                    select(TrendSignal).where(
                        TrendSignal.keyword == trend["keyword"],
                        TrendSignal.captured_at == trend["captured_at"],
                    )
                )
                signal = result.scalar_one_or_none()
                if signal is None:
                    continue

                for article_data in trend["articles"]:
                    source_id = await _resolve_source(session, article_data["url"])
                    if source_id is None:
                        logger.debug(
                            "trends: skipping article url=%s (no source match)", article_data["url"]
                        )
                        continue

                    article_stmt = pg_insert(Article).values(
                        source_id=source_id,
                        title=article_data["title"],
                        url=article_data["url"],
                        published_at=None,
                    )
                    article_stmt = article_stmt.on_conflict_do_nothing(index_elements=["url"])
                    await session.execute(article_stmt)

                    article_result = await session.execute(
                        select(Article).where(Article.url == article_data["url"])
                    )
                    article = article_result.scalar_one_or_none()
                    if article is None:
                        continue

                    join_stmt = pg_insert(TrendSignalArticle).values(
                        trend_signal_id=signal.id,
                        article_id=article.id,
                    )
                    join_stmt = join_stmt.on_conflict_do_nothing(constraint="trend_signal_article_pkey")
                    await session.execute(join_stmt)

                total_signals += 1

    logger.info("trends: processed %d trending topics", total_signals)
    return total_signals
