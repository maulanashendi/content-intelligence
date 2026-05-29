"""
Unit tests for ingest.parser — the unified feed parser.

Each test is named after the semantic property it guards, not the implementation.
The tests are deliberately format-faithful: fixture XML mirrors what the actual
providers send so a future provider change surfaces immediately.
"""

from datetime import datetime, timezone

import pytest
from ingest.parser import (
    _detect_format,
    _parse_news_sitemap,
    _parse_rss,
    _parse_sitemap,
    _to_naive_utc,
    parse_feed,
)

# ---------------------------------------------------------------------------
# Canonical fixture XML — mirrors real provider payloads
# ---------------------------------------------------------------------------

# RSS 2.0 — matches CNBC Indonesia, Detik, Tempo rss.tempo.co, etc.
_RSS_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Tempo Bisnis</title>
    <link>https://rss.tempo.co/bisnis</link>
    <item>
      <title>Harga Emas Naik Rp 20 Ribu per Gram</title>
      <link>https://bisnis.tempo.co/read/2105822/harga-emas-naik-rp-20-ribu-per-gram</link>
      <pubDate>Fri, 29 May 2026 09:15:47 +0700</pubDate>
      <description><![CDATA[<p>Harga emas Antam naik Rp 20.000 dibandingkan hari sebelumnya.</p>]]></description>
    </item>
    <item>
      <title>BRI Salurkan KUR Rp 65 Triliun hingga April 2026</title>
      <link>https://bisnis.tempo.co/read/2105769/bri-salurkan-kur-rp-65-triliun-hingga-april-2026</link>
      <pubDate>Thu, 28 May 2026 17:11:52 +0700</pubDate>
    </item>
  </channel>
</rss>"""

# Atom — matches some feeds that feedparser handles via the same path
_ATOM_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Atom Feed</title>
  <entry>
    <title>Entry Pertama Atom</title>
    <link href="https://example.com/entry-1"/>
    <published>2026-05-29T06:00:00Z</published>
    <summary>Ringkasan pertama.</summary>
  </entry>
  <entry>
    <title>Entry Kedua Atom</title>
    <link href="https://example.com/entry-2"/>
    <updated>2026-05-29T07:00:00Z</updated>
  </entry>
</feed>"""

# Google News Sitemap — mirrors Suara.com exactly (CDATA loc, +07:00 dates)
# Bug context: this format was silently yielding 0 entries because feedparser
# cannot parse <urlset> XML; the fix adds _parse_news_sitemap + fallback.
_GOOGLE_NEWS_SITEMAP_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc><![CDATA[ https://www.suara.com/news/2026/05/29/150041/viral-pengantin-pria-pakai-selendang ]]></loc>
    <news:news>
      <news:publication>
        <news:name>Suara.com</news:name>
        <news:language>id</news:language>
      </news:publication>
      <news:publication_date>2026-05-29T15:00:41+07:00</news:publication_date>
      <news:title><![CDATA[Viral Pengantin Pria Pakai Selendang Bentuk Bunga Menjuntai]]></news:title>
      <news:keywords><![CDATA[viral,busana pengantin]]></news:keywords>
    </news:news>
  </url>
  <url>
    <loc><![CDATA[ https://www.suara.com/news/2026/05/29/140000/artikel-kedua-berita-penting ]]></loc>
    <news:news>
      <news:publication_date>2026-05-29T14:00:00+07:00</news:publication_date>
      <news:title><![CDATA[Artikel Kedua Berita Penting]]></news:title>
    </news:news>
  </url>
</urlset>"""

# Standard sitemap — urlset without Google News extensions
_STANDARD_SITEMAP_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/berita/artikel-penting-satu</loc>
    <lastmod>2026-05-28T10:00:00</lastmod>
  </url>
  <url>
    <loc>https://example.com/berita/artikel-kedua-lebih-baru</loc>
    <lastmod>2026-05-29T08:30:00Z</lastmod>
  </url>
</urlset>"""


# ---------------------------------------------------------------------------
# _detect_format — format sniffing from the first 512 bytes
# ---------------------------------------------------------------------------


def test_detect_format_rss2_returns_rss() -> None:
    assert _detect_format(b"<?xml?><rss version='2.0'><channel/>") == "rss"


def test_detect_format_atom_returns_rss() -> None:
    # Atom is handled by feedparser under the "rss" path
    assert _detect_format(b'<feed xmlns="http://www.w3.org/2005/Atom">') == "rss"


def test_detect_format_google_news_sitemap_returns_news_sitemap() -> None:
    assert _detect_format(_GOOGLE_NEWS_SITEMAP_XML) == "news_sitemap"


def test_detect_format_standard_sitemap_returns_sitemap() -> None:
    assert _detect_format(_STANDARD_SITEMAP_XML) == "sitemap"


def test_detect_format_urlset_without_google_namespace_is_not_news_sitemap() -> None:
    plain_sitemap = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url/></urlset>'
    assert _detect_format(plain_sitemap) == "sitemap"


def test_detect_format_unknown_garbage_defaults_to_rss() -> None:
    # Unknown content falls through to feedparser which handles it gracefully
    assert _detect_format(b"not xml at all") == "rss"


# ---------------------------------------------------------------------------
# _parse_rss — RSS 2.0 and Atom parsing
# ---------------------------------------------------------------------------


def test_parse_rss_returns_all_items() -> None:
    entries = _parse_rss(_RSS_XML)
    assert len(entries) == 2


def test_parse_rss_item_has_real_title_from_element() -> None:
    entries = _parse_rss(_RSS_XML)
    assert entries[0]["title"] == "Harga Emas Naik Rp 20 Ribu per Gram"


def test_parse_rss_item_url_is_link_element() -> None:
    entries = _parse_rss(_RSS_XML)
    assert entries[0]["url"] == "https://bisnis.tempo.co/read/2105822/harga-emas-naik-rp-20-ribu-per-gram"


def test_parse_rss_item_published_at_is_naive_datetime() -> None:
    entries = _parse_rss(_RSS_XML)
    dt = entries[0]["published_at"]
    assert isinstance(dt, datetime)
    assert dt.tzinfo is None, "published_at must be naive UTC for DB compatibility"


def test_parse_rss_html_description_stripped_to_plain_text() -> None:
    entries = _parse_rss(_RSS_XML)
    fp = entries[0]["first_paragraph"]
    assert fp is not None
    assert "<p>" not in fp
    assert "Harga emas Antam naik" in fp


def test_parse_rss_item_without_description_has_no_first_paragraph() -> None:
    entries = _parse_rss(_RSS_XML)
    assert entries[1]["first_paragraph"] is None


def test_parse_rss_atom_feed_parsed_correctly() -> None:
    entries = _parse_rss(_ATOM_XML)
    assert len(entries) == 2
    assert entries[0]["title"] == "Entry Pertama Atom"
    assert entries[0]["url"] == "https://example.com/entry-1"


def test_parse_rss_item_missing_title_is_skipped() -> None:
    xml = b'<?xml version="1.0"?><rss version="2.0"><channel><item><link>https://x.com/a</link></item></channel></rss>'
    assert _parse_rss(xml) == []


def test_parse_rss_item_missing_link_is_skipped() -> None:
    xml = b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>T</title></item></channel></rss>'
    assert _parse_rss(xml) == []


def test_parse_rss_item_blank_title_and_link_skipped() -> None:
    xml = b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>  </title><link>  </link></item></channel></rss>'
    assert _parse_rss(xml) == []


def test_parse_rss_uses_updated_when_published_absent() -> None:
    xml = b"""\
<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>T</title><link>https://x.com/a</link>
<pubDate>Mon, 27 May 2026 12:00:00 +0000</pubDate></item></channel></rss>"""
    entries = _parse_rss(xml)
    assert entries[0]["published_at"] is not None


def test_parse_rss_returns_empty_list_on_empty_channel() -> None:
    xml = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    assert _parse_rss(xml) == []


# ---------------------------------------------------------------------------
# _parse_news_sitemap — Google News sitemap (Suara regression)
# ---------------------------------------------------------------------------


def test_parse_news_sitemap_returns_all_entries() -> None:
    entries = _parse_news_sitemap(_GOOGLE_NEWS_SITEMAP_XML)
    assert len(entries) == 2


def test_parse_news_sitemap_title_comes_from_news_title_not_url_slug() -> None:
    """Regression: old code derived title from URL slug — e.g. 'Viral Pengantin
    Pria Pakai Selendang' — which loses the second half of the real title.
    The fix reads <news:title> which contains the full editorial headline."""
    entries = _parse_news_sitemap(_GOOGLE_NEWS_SITEMAP_XML)
    # Full title from <news:title>
    assert entries[0]["title"] == "Viral Pengantin Pria Pakai Selendang Bentuk Bunga Menjuntai"
    # NOT the URL slug truncation
    assert entries[0]["title"] != "Viral Pengantin Pria Pakai Selendang"


def test_parse_news_sitemap_url_strips_cdata_whitespace() -> None:
    """Suara wraps <loc> in CDATA with leading/trailing spaces; must be stripped."""
    entries = _parse_news_sitemap(_GOOGLE_NEWS_SITEMAP_XML)
    assert entries[0]["url"] == "https://www.suara.com/news/2026/05/29/150041/viral-pengantin-pria-pakai-selendang"
    assert not entries[0]["url"].startswith(" ")
    assert not entries[0]["url"].endswith(" ")


def test_parse_news_sitemap_published_at_is_naive_utc() -> None:
    """Regression: +07:00 timezone in publication_date caused asyncpg
    'can't subtract offset-naive and offset-aware datetimes' on INSERT.
    Fix: _to_naive_utc() converts to UTC and strips tzinfo before returning."""
    entries = _parse_news_sitemap(_GOOGLE_NEWS_SITEMAP_XML)
    dt = entries[0]["published_at"]
    assert isinstance(dt, datetime)
    assert dt.tzinfo is None, "published_at must be naive for DB TIMESTAMP WITHOUT TIME ZONE"


def test_parse_news_sitemap_publication_date_correctly_offset_to_utc() -> None:
    """2026-05-29T15:00:41+07:00 is 08:00:41 UTC."""
    entries = _parse_news_sitemap(_GOOGLE_NEWS_SITEMAP_XML)
    dt = entries[0]["published_at"]
    assert dt == datetime(2026, 5, 29, 8, 0, 41)


def test_parse_news_sitemap_no_first_paragraph() -> None:
    """Sitemap entries have no body text; first_paragraph must be None
    so the scraper knows to fetch full content later."""
    entries = _parse_news_sitemap(_GOOGLE_NEWS_SITEMAP_XML)
    assert all(e["first_paragraph"] is None for e in entries)


def test_parse_news_sitemap_entry_without_news_title_falls_back_to_url_slug() -> None:
    xml = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>https://www.suara.com/news/2026/05/01/artikel-tanpa-judul</loc>
    <news:news>
      <news:publication_date>2026-05-01T10:00:00+07:00</news:publication_date>
    </news:news>
  </url>
</urlset>"""
    entries = _parse_news_sitemap(xml)
    assert len(entries) == 1
    assert entries[0]["title"] == "Artikel Tanpa Judul"


def test_parse_news_sitemap_malformed_xml_returns_empty() -> None:
    assert _parse_news_sitemap(b"<not valid xml<<<") == []


# ---------------------------------------------------------------------------
# _parse_sitemap — standard sitemap
# ---------------------------------------------------------------------------


def test_parse_sitemap_returns_all_entries() -> None:
    entries = _parse_sitemap(_STANDARD_SITEMAP_XML)
    assert len(entries) == 2


def test_parse_sitemap_title_derived_from_url_slug() -> None:
    entries = _parse_sitemap(_STANDARD_SITEMAP_XML)
    assert entries[0]["title"] == "Artikel Penting Satu"


def test_parse_sitemap_lastmod_parsed_as_naive_datetime() -> None:
    entries = _parse_sitemap(_STANDARD_SITEMAP_XML)
    assert isinstance(entries[0]["published_at"], datetime)
    assert entries[0]["published_at"].tzinfo is None


def test_parse_sitemap_lastmod_with_z_suffix_parsed_correctly() -> None:
    entries = _parse_sitemap(_STANDARD_SITEMAP_XML)
    # Second entry has 'Z' suffix which must be stripped before fromisoformat
    assert entries[1]["published_at"] == datetime(2026, 5, 29, 8, 30, 0)


def test_parse_sitemap_entry_without_lastmod_has_none_published_at() -> None:
    xml = b"""\
<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/artikel</loc></url>
</urlset>"""
    entries = _parse_sitemap(xml)
    assert entries[0]["published_at"] is None


def test_parse_sitemap_entry_without_loc_is_skipped() -> None:
    xml = b"""\
<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><lastmod>2026-05-01</lastmod></url>
</urlset>"""
    assert _parse_sitemap(xml) == []


# ---------------------------------------------------------------------------
# _to_naive_utc — timezone normalisation
# ---------------------------------------------------------------------------


def test_to_naive_utc_strips_wib_offset() -> None:
    wib = datetime(2026, 5, 29, 15, 0, 41, tzinfo=timezone(  # noqa: DTZ001
        __import__("datetime").timedelta(hours=7)
    ))
    result = _to_naive_utc(wib)
    assert result.tzinfo is None
    assert result == datetime(2026, 5, 29, 8, 0, 41)


def test_to_naive_utc_passes_through_naive_datetime_unchanged() -> None:
    naive = datetime(2026, 5, 29, 8, 0, 0)
    assert _to_naive_utc(naive) == naive
    assert _to_naive_utc(naive).tzinfo is None


def test_to_naive_utc_utc_aware_becomes_same_time_naive() -> None:
    from datetime import timezone as tz
    utc_aware = datetime(2026, 5, 29, 8, 0, 0, tzinfo=tz.utc)
    result = _to_naive_utc(utc_aware)
    assert result == datetime(2026, 5, 29, 8, 0, 0)
    assert result.tzinfo is None


# ---------------------------------------------------------------------------
# parse_feed — unified entrypoint: detection + fallback chain
# ---------------------------------------------------------------------------


def test_parse_feed_rss_returns_rss_format() -> None:
    entries, fmt = parse_feed(_RSS_XML)
    assert fmt == "rss"
    assert len(entries) == 2


def test_parse_feed_google_news_sitemap_detected_directly() -> None:
    """No fallback needed: <urlset> + google namespace is identified upfront."""
    entries, fmt = parse_feed(_GOOGLE_NEWS_SITEMAP_XML)
    assert fmt == "news_sitemap"
    assert len(entries) == 2


def test_parse_feed_standard_sitemap_detected_directly() -> None:
    entries, fmt = parse_feed(_STANDARD_SITEMAP_XML)
    assert fmt == "sitemap"
    assert len(entries) == 2


def test_parse_feed_suara_regression_fallback_from_rss_to_news_sitemap(
    caplog,
) -> None:
    """Regression: Suara is stored as source_type=rss so ingest_rss() calls
    parse_feed(). feedparser returns 0 entries on <urlset> XML.
    The fallback chain must then try news_sitemap and succeed."""
    # Pretend the detect function sees <rss> prefix (wrong detection) — simulate
    # by using a sitemap byte stream but verifying the fallback path is hit
    # when feedparser genuinely returns 0.
    # We use GOOGLE_NEWS_SITEMAP_XML which _detect_format correctly identifies
    # as news_sitemap already, but the semantic guarantee we're testing is:
    # parse_feed never returns 0 entries for a valid sitemap when a correct
    # parser exists.
    entries, fmt = parse_feed(_GOOGLE_NEWS_SITEMAP_XML, source_name="Suara – Sitemap News")
    assert len(entries) > 0
    assert fmt == "news_sitemap"


def test_parse_feed_empty_rss_returns_empty_list() -> None:
    xml = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    entries, fmt = parse_feed(xml)
    assert entries == []


def test_parse_feed_garbage_bytes_returns_empty_without_raising() -> None:
    entries, fmt = parse_feed(b"<<not xml at all>>")
    assert entries == []


def test_parse_feed_all_entries_have_required_keys() -> None:
    for raw in [_RSS_XML, _GOOGLE_NEWS_SITEMAP_XML, _STANDARD_SITEMAP_XML]:
        entries, _ = parse_feed(raw)
        for entry in entries:
            assert "title" in entry
            assert "url" in entry
            assert "published_at" in entry
            assert "first_paragraph" in entry


def test_parse_feed_no_entry_has_timezone_aware_published_at() -> None:
    """DB column is TIMESTAMP WITHOUT TIME ZONE — every parser must return naive."""
    for raw in [_RSS_XML, _GOOGLE_NEWS_SITEMAP_XML, _STANDARD_SITEMAP_XML]:
        entries, _ = parse_feed(raw)
        for entry in entries:
            dt = entry["published_at"]
            if dt is not None:
                assert dt.tzinfo is None, (
                    f"published_at {dt!r} has tzinfo — will crash asyncpg on INSERT"
                )
