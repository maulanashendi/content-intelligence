import logging
import math
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from core.db import get_session
from core.models import (
    Article,
    ContentSource,
    ScrapeStatus,
    TrendSignal,
    TrendSignalArticle,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=ID"

_HT_NS = "https://trends.google.com/trending/rss"
_LOG_NORM_DENOM = math.log1p(1_000_000.0)


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
        raw_traffic = float(raw) * multiplier
        # Log-scale to 0-100 so scoring velocity.py, which clips at 100 before
        # normalising to [0,1], receives a differentiated signal (1K≈50,
        # 100K≈83, 1M=100) rather than every trend clamped to 100.
        return round(min(math.log1p(raw_traffic) / _LOG_NORM_DENOM * 100.0, 100.0), 2)
    except ValueError:
        return None


def _parse_trends_feed(xml_text: str, now: datetime) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("trends: failed to parse XML feed")
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    trends = []
    for item in channel.findall("item"):
        keyword = (item.findtext("title") or "").strip()
        if not keyword:
            continue

        approx_traffic = item.findtext(f"{{{_HT_NS}}}approx_traffic")
        interest_score = _extract_traffic_number(approx_traffic)

        related_urls = []
        for news_item in item.findall(f"{{{_HT_NS}}}news_item"):
            title = (news_item.findtext(f"{{{_HT_NS}}}news_item_title") or "").strip()
            url = (news_item.findtext(f"{{{_HT_NS}}}news_item_url") or "").strip()
            if title and url:
                related_urls.append({"title": title, "url": url})

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
    parts = host.split(".")
    # Strip subdomains (e.g. "finance.detik.com" → "detik.com") so article-page
    # URLs match against RSS-feed ContentSource rows that share the base domain.
    # For ccTLD+SLD combos like "co.id" the second-to-last label is ≤3 chars, so
    # we keep three labels (e.g. "kontan.co.id") instead of two.
    if len(parts) >= 3 and len(parts[-2]) <= 3:
        base_domain = ".".join(parts[-3:])
    elif len(parts) >= 2:
        base_domain = ".".join(parts[-2:])
    else:
        base_domain = host
    result = await session.execute(
        select(ContentSource).where(ContentSource.url.ilike(f"%{base_domain}%"))
    )
    source = result.scalars().first()
    return source.id if source else None


async def ingest_trends(client: httpx.AsyncClient) -> int:
    """One transaction per trend keyword so a failure on one does not roll back earlier writes."""
    try:
        resp = await client.get(TRENDS_RSS_URL)
        resp.raise_for_status()
    except Exception:
        logger.exception("failed to fetch Google Trends RSS")
        return 0

    now = datetime.now(UTC).replace(tzinfo=None)
    parsed_trends = _parse_trends_feed(resp.text, now)
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
                        scrape_status=ScrapeStatus.pending,
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
                    join_stmt = join_stmt.on_conflict_do_nothing(
                        constraint="trend_signal_article_pkey"
                    )
                    await session.execute(join_stmt)

                total_signals += 1

    logger.info("trends: processed %d trending topics", total_signals)
    return total_signals
