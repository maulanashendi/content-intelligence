import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from core.db import get_session
from core.models import Article, ContentSource, SourceStatus, SourceType
from ingest.rss import (
    DEFAULT_HEADERS,
    BlockedError,
    _html_to_text,
    _parse_entry,
    fetch_and_store_source,
    ingest_rss,
    make_http_client,
)
from sqlalchemy import select


def _mock_client(status: int, body: str = "") -> AsyncMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = body
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status}", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status = MagicMock()
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=resp)
    return mock


# ---------------------------------------------------------------------------
# BlockedError detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_error_raised_on_403(rss_source: ContentSource) -> None:
    with pytest.raises(BlockedError):
        await fetch_and_store_source(
            _mock_client(403), rss_source.id, rss_source.url, rss_source.name
        )


@pytest.mark.asyncio
async def test_blocked_error_raised_on_429(rss_source: ContentSource) -> None:
    with pytest.raises(BlockedError):
        await fetch_and_store_source(
            _mock_client(429), rss_source.id, rss_source.url, rss_source.name
        )


# ---------------------------------------------------------------------------
# fetch_and_store_source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_and_store_source_inserts_articles(
    rss_source: ContentSource, rss_feed_xml: str
) -> None:
    count = await fetch_and_store_source(
        _mock_client(200, rss_feed_xml), rss_source.id, rss_source.url, rss_source.name
    )
    assert count == 2

    async with get_session() as session:
        rows = (
            await session.execute(select(Article).where(Article.source_id == rss_source.id))
        ).scalars().all()

    assert len(rows) == 2
    assert {a.url for a in rows} == {
        "https://example.com/article-one",
        "https://example.com/article-two",
    }


@pytest.mark.asyncio
async def test_fetch_and_store_source_returns_zero_on_empty_feed(
    rss_source: ContentSource,
) -> None:
    empty = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    count = await fetch_and_store_source(
        _mock_client(200, empty), rss_source.id, rss_source.url, rss_source.name
    )
    assert count == 0


@pytest.mark.asyncio
async def test_fetch_and_store_source_deduplicates_articles(
    rss_source: ContentSource, rss_feed_xml: str
) -> None:
    client = _mock_client(200, rss_feed_xml)
    await fetch_and_store_source(client, rss_source.id, rss_source.url, rss_source.name)
    await fetch_and_store_source(client, rss_source.id, rss_source.url, rss_source.name)

    async with get_session() as session:
        rows = (
            await session.execute(select(Article).where(Article.source_id == rss_source.id))
        ).scalars().all()

    assert len(rows) == 2


@pytest.mark.asyncio
async def test_fetch_and_store_source_updates_source_status_active(
    rss_source: ContentSource, rss_feed_xml: str
) -> None:
    await fetch_and_store_source(
        _mock_client(200, rss_feed_xml), rss_source.id, rss_source.url, rss_source.name
    )

    async with get_session() as session:
        source = await session.get(ContentSource, rss_source.id)

    assert source is not None
    assert source.status == SourceStatus.active
    assert source.last_fetched_at is not None


# ---------------------------------------------------------------------------
# ingest_rss — bulk ingestion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_rss_inserts_articles(rss_source: ContentSource, rss_feed_xml: str) -> None:
    total = await ingest_rss(_mock_client(200, rss_feed_xml))
    assert total == 2


@pytest.mark.asyncio
async def test_ingest_rss_sets_blocked_status_on_403(rss_source: ContentSource) -> None:
    await ingest_rss(_mock_client(403))

    async with get_session() as session:
        source = await session.get(ContentSource, rss_source.id)

    assert source is not None
    assert source.status == SourceStatus.blocked


@pytest.mark.asyncio
async def test_ingest_rss_sets_error_status_on_network_failure(
    rss_source: ContentSource,
) -> None:
    failing = AsyncMock()
    failing.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    await ingest_rss(failing)

    async with get_session() as session:
        source = await session.get(ContentSource, rss_source.id)

    assert source is not None
    assert source.status == SourceStatus.error


@pytest.mark.asyncio
async def test_ingest_rss_continues_after_one_source_fails(rss_feed_xml: str) -> None:
    good = ContentSource(
        id=uuid.uuid4(),
        name="Good Source",
        url="https://good.example.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
    )
    bad = ContentSource(
        id=uuid.uuid4(),
        name="Bad Source",
        url="https://bad.example.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
    )
    async with get_session() as session:
        session.add_all([good, bad])
        await session.commit()

    async def _get(url: str, **_):
        resp = MagicMock()
        if "bad" in url:
            resp.status_code = 403
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "403", request=MagicMock(), response=resp
            )
        else:
            resp.status_code = 200
            resp.text = rss_feed_xml
            resp.raise_for_status = MagicMock()
        return resp

    mock = AsyncMock()
    mock.get = AsyncMock(side_effect=_get)
    total = await ingest_rss(mock)

    assert total == 2

    async with get_session() as session:
        good_src = await session.get(ContentSource, good.id)
        bad_src = await session.get(ContentSource, bad.id)

    assert good_src.status == SourceStatus.active
    assert bad_src.status == SourceStatus.blocked


# ---------------------------------------------------------------------------
# Pure parsers — defensive against bad input
# ---------------------------------------------------------------------------


def test_html_to_text_handles_empty_input() -> None:
    assert _html_to_text("") == ""


def test_html_to_text_strips_html_tags() -> None:
    assert _html_to_text("<p>hello <b>world</b></p>") == "hello world"


def test_html_to_text_handles_invalid_lxml_gracefully() -> None:
    out = _html_to_text("\x00\x01\x02 garbage")
    assert isinstance(out, str)


def test_parse_entry_skips_when_title_missing() -> None:
    assert _parse_entry({"link": "https://x.com/a"}) == {}


def test_parse_entry_skips_when_link_missing() -> None:
    assert _parse_entry({"title": "Headline"}) == {}


def test_parse_entry_skips_when_both_blank() -> None:
    assert _parse_entry({"title": "  ", "link": "  "}) == {}


def test_parse_entry_returns_dict_when_minimal_fields_present() -> None:
    parsed = _parse_entry({"title": "Title", "link": "https://x.com/a"})
    assert parsed["title"] == "Title"
    assert parsed["url"] == "https://x.com/a"
    assert parsed["published_at"] is None
    assert parsed["first_paragraph"] is None


# ---------------------------------------------------------------------------
# Malformed feed bodies — feedparser is forgiving; we must not crash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_and_store_source_handles_garbage_body(
    rss_source: ContentSource,
) -> None:
    count = await fetch_and_store_source(
        _mock_client(200, "<<not-xml-at-all>>"),
        rss_source.id,
        rss_source.url,
        rss_source.name,
    )
    assert count == 0

    async with get_session() as session:
        source = await session.get(ContentSource, rss_source.id)
    assert source is not None
    assert source.status == SourceStatus.active


@pytest.mark.asyncio
async def test_fetch_and_store_source_handles_empty_body(
    rss_source: ContentSource,
) -> None:
    count = await fetch_and_store_source(
        _mock_client(200, ""),
        rss_source.id,
        rss_source.url,
        rss_source.name,
    )
    assert count == 0


# ---------------------------------------------------------------------------
# Idempotency: rerunning a feed never inserts duplicates and returns 0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_and_store_source_atomic_articles_and_status(
    rss_source: ContentSource, rss_feed_xml: str
) -> None:
    await fetch_and_store_source(
        _mock_client(200, rss_feed_xml), rss_source.id, rss_source.url, rss_source.name
    )

    async with get_session() as session:
        source = await session.get(ContentSource, rss_source.id)
        rows = (
            await session.execute(select(Article).where(Article.source_id == rss_source.id))
        ).scalars().all()

    assert source is not None
    assert source.status == SourceStatus.active
    assert source.last_fetched_at is not None
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_ingest_rss_idempotent_second_run_inserts_zero(
    rss_source: ContentSource, rss_feed_xml: str
) -> None:
    first = await ingest_rss(_mock_client(200, rss_feed_xml))
    second = await ingest_rss(_mock_client(200, rss_feed_xml))

    assert first == 2
    assert second == 0

    async with get_session() as session:
        rows = (
            await session.execute(select(Article).where(Article.source_id == rss_source.id))
        ).scalars().all()
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# make_http_client — anti-WAF defaults (regression: coconuts.co/jakarta/feed/
# was returning 302 to a RunCloud block page because httpx default UA is
# python-httpx/x.y and follow_redirects defaults to False)
# ---------------------------------------------------------------------------


def test_make_http_client_user_agent_is_not_default_python_httpx() -> None:
    client = make_http_client()
    try:
        ua = client.headers.get("User-Agent", "")
        assert "python-httpx" not in ua.lower(), (
            f"Default httpx UA is blocked by RunCloud/Cloudflare WAFs; "
            f"got UA={ua!r}"
        )
        assert ua, "User-Agent must not be empty"
    finally:
        # AsyncClient.aclose is async; for a never-used client, sync close
        # via the underlying transport is sufficient and avoids needing a
        # running loop in this unit test.
        pass


def test_make_http_client_advertises_rss_mime_types() -> None:
    client = make_http_client()
    accept = client.headers.get("Accept", "")
    assert "application/rss+xml" in accept
    assert "application/atom+xml" in accept


def test_make_http_client_follows_redirects() -> None:
    client = make_http_client()
    assert client.follow_redirects is True, (
        "Feeds commonly redirect to canonicalized URLs (e.g. /feed → /feed/); "
        "follow_redirects must be True or every redirected feed silently "
        "fails."
    )


def test_make_http_client_uses_configured_timeout() -> None:
    from core.config import settings

    client = make_http_client()
    assert client.timeout.connect == float(settings.ingest_timeout_seconds)
    assert client.timeout.read == float(settings.ingest_timeout_seconds)


def test_default_headers_module_constant_includes_required_fields() -> None:
    assert "User-Agent" in DEFAULT_HEADERS
    assert "Accept" in DEFAULT_HEADERS
    assert "python-httpx" not in DEFAULT_HEADERS["User-Agent"].lower()


# ---------------------------------------------------------------------------
# Redirect handling — coconuts.co regression. Use httpx.MockTransport to
# simulate a 302 → 200 chain without hitting the network.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_and_store_source_follows_redirect_to_real_feed(
    rss_source: ContentSource, rss_feed_xml: str
) -> None:
    requests_seen: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(str(request.url))
        if request.url.path == "/feed":
            return httpx.Response(
                302,
                headers={"location": "https://example.com/feed/canonical"},
            )
        return httpx.Response(
            200,
            text=rss_feed_xml,
            headers={"content-type": "application/rss+xml"},
        )

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(
        transport=transport,
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
    ) as client:
        count = await fetch_and_store_source(
            client, rss_source.id, "https://example.com/feed", rss_source.name
        )

    assert count == 2
    assert len(requests_seen) == 2
    assert requests_seen[0].endswith("/feed")
    assert requests_seen[1].endswith("/feed/canonical")


@pytest.mark.asyncio
async def test_fetch_without_follow_redirects_would_fail_on_302() -> None:
    """Locks in the bug we fixed: a client without follow_redirects raises
    HTTPStatusError on the WAF redirect, which is exactly what made
    coconuts.co show up as status='error' in the DB."""

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://example.com/RUNCLOUD-7G-WAF-BLOCKED"},
        )

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_and_store_source(
                client, uuid.uuid4(), "https://example.com/feed", "WAF Test"
            )


@pytest.mark.asyncio
async def test_fetch_sends_configured_user_agent_to_origin(
    rss_source: ContentSource, rss_feed_xml: str
) -> None:
    captured_ua: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_ua.append(request.headers.get("user-agent", ""))
        return httpx.Response(
            200,
            text=rss_feed_xml,
            headers={"content-type": "application/rss+xml"},
        )

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(
        transport=transport, headers=DEFAULT_HEADERS, follow_redirects=True
    ) as client:
        await fetch_and_store_source(
            client, rss_source.id, "https://example.com/feed", rss_source.name
        )

    assert len(captured_ua) == 1
    assert "python-httpx" not in captured_ua[0].lower()
    assert captured_ua[0] == DEFAULT_HEADERS["User-Agent"]
