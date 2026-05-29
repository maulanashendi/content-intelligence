import contextlib
import logging
from datetime import UTC, datetime

import feedparser
from lxml import etree
from lxml import html as lxml_html

logger = logging.getLogger(__name__)

_NS_SITEMAP = "http://www.sitemaps.org/schemas/sitemap/0.9"
_NS_NEWS = "http://www.google.com/schemas/sitemap-news/0.9"


def _to_naive_utc(dt: datetime) -> datetime:
    """Convert any datetime to naive UTC, as the DB column is TIMESTAMP WITHOUT TIME ZONE."""
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _detect_format(raw: bytes) -> str:
    """Return 'rss', 'sitemap', or 'news_sitemap' from the first 512 bytes."""
    prefix = raw[:512].lower()
    if b"<rss" in prefix or b"<feed" in prefix:
        return "rss"
    if b"<urlset" in prefix:
        if b"google.com/schemas/sitemap-news" in prefix:
            return "news_sitemap"
        return "sitemap"
    return "rss"  # fallback: let feedparser attempt


def _parse_rss(raw: bytes) -> list[dict]:
    feed = feedparser.parse(raw)
    entries = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue

        published_at = None
        for attr in ("published_parsed", "updated_parsed"):
            time_struct = entry.get(attr)
            if time_struct:
                with contextlib.suppress(TypeError, ValueError):
                    published_at = datetime(*time_struct[:6])
                    break

        summary = (entry.get("summary") or "").strip()
        first_paragraph = None
        if summary:
            try:
                first_paragraph = lxml_html.fromstring(summary).text_content().strip()[:2000] or None
            except Exception:
                first_paragraph = summary[:2000] or None

        entries.append(
            {
                "title": title,
                "url": link,
                "published_at": published_at,
                "first_paragraph": first_paragraph,
            }
        )
    return entries


def _parse_sitemap(raw: bytes) -> list[dict]:
    """Standard sitemap: <urlset><url><loc> + <lastmod>."""
    try:
        tree = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []
    ns = {"sm": _NS_SITEMAP}
    entries = []
    for url_el in tree.findall("sm:url", ns):
        loc = url_el.find("sm:loc", ns)
        if loc is None or not (loc.text or "").strip():
            continue

        lastmod = url_el.find("sm:lastmod", ns)
        published_at = None
        if lastmod is not None and (lastmod.text or "").strip():
            with contextlib.suppress(ValueError, TypeError):
                published_at = _to_naive_utc(datetime.fromisoformat(lastmod.text.strip().rstrip("Z")))

        url = loc.text.strip()
        title = url.rstrip("/").split("/")[-1].replace("-", " ").title()
        entries.append({"title": title, "url": url, "published_at": published_at, "first_paragraph": None})
    return entries


def _parse_news_sitemap(raw: bytes) -> list[dict]:
    """Google News sitemap: <urlset xmlns:news=...><url><loc> + <news:title> + <news:publication_date>."""
    try:
        tree = etree.fromstring(raw)
    except etree.XMLSyntaxError:
        return []
    ns = {"sm": _NS_SITEMAP, "news": _NS_NEWS}
    entries = []
    for url_el in tree.findall("sm:url", ns):
        loc = url_el.find("sm:loc", ns)
        if loc is None or not (loc.text or "").strip():
            continue

        # prefer <news:title> over URL slug
        news_title_el = url_el.find("news:news/news:title", ns)
        if news_title_el is not None and (news_title_el.text or "").strip():
            title = news_title_el.text.strip()
        else:
            url_str = (loc.text or "").strip()
            title = url_str.rstrip("/").split("/")[-1].replace("-", " ").title()

        pub_date_el = url_el.find("news:news/news:publication_date", ns)
        published_at = None
        if pub_date_el is not None and (pub_date_el.text or "").strip():
            with contextlib.suppress(ValueError, TypeError):
                published_at = _to_naive_utc(datetime.fromisoformat(pub_date_el.text.strip()))

        url = loc.text.strip()
        entries.append({"title": title, "url": url, "published_at": published_at, "first_paragraph": None})
    return entries


_PARSERS = {
    "rss": _parse_rss,
    "sitemap": _parse_sitemap,
    "news_sitemap": _parse_news_sitemap,
}

# Fallback order: if primary returns 0 entries, try these in order
_FALLBACK_ORDER = ["rss", "news_sitemap", "sitemap"]


def parse_feed(raw: bytes, source_name: str = "") -> tuple[list[dict], str]:
    """Auto-detect format and parse. Falls back through all formats if 0 entries.

    Returns (entries, format_used).
    """
    primary = _detect_format(raw)
    entries = _PARSERS[primary](raw)
    if entries:
        return entries, primary

    for fmt in _FALLBACK_ORDER:
        if fmt == primary:
            continue
        entries = _PARSERS[fmt](raw)
        if entries:
            logger.info(
                "parser_fallback source=%s primary=%s fallback=%s entries=%d",
                source_name,
                primary,
                fmt,
                len(entries),
            )
            return entries, fmt

    return [], primary
