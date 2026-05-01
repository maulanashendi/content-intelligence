"""
Tests for /api/v1/sources CRUD endpoints.

Note on pg_notify in tests: the API test session wraps all DB operations in an
outer transaction that is rolled back after each test. PostgreSQL only delivers
LISTEN/NOTIFY after the *outermost* transaction commits — so the pg_notify call
executes successfully but is silently discarded during test teardown. No stubs
needed for correctness; spy tests verify the call was issued.
"""

import uuid
from datetime import UTC, datetime, timedelta
from sqlalchemy import text as real_text
from unittest.mock import patch

import pytest
from core.models import Article, ContentSource, SourceStatus, SourceType
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_source(
    session: AsyncSession,
    *,
    url: str = "https://seed.example.com/feed",
    name: str = "Seed Source",
    is_enabled: bool = True,
) -> ContentSource:
    source = ContentSource(
        name=name,
        url=url,
        source_type=SourceType.rss,
        is_enabled=is_enabled,
    )
    session.add(source)
    await session.flush()
    await session.refresh(source)
    return source


async def _seed_article(session: AsyncSession, source_id: uuid.UUID) -> Article:
    article = Article(
        source_id=source_id,
        title="Seed Article",
        url=f"https://seed.example.com/article-{uuid.uuid4()}",
    )
    session.add(article)
    await session.flush()
    return article


# ---------------------------------------------------------------------------
# GET /sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sources_returns_empty_list(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_sources_returns_seeded_source(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_source(session, url="https://listed.example.com/feed", name="Listed")
    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Listed"
    assert data[0]["url"] == "https://listed.example.com/feed"
    assert data[0]["source_type"] == "rss"
    assert "article_count_24h" in data[0]


@pytest.mark.asyncio
async def test_list_sources_ordered_by_name(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_source(session, url="https://z.example.com/feed", name="Zzz")
    await _seed_source(session, url="https://a.example.com/feed", name="Aaa")
    resp = await client.get("/api/v1/sources")
    names = [s["name"] for s in resp.json()]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# POST /sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_source_returns_201(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/sources",
        json={"url": "https://new.example.com/feed", "name": "New Feed"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["url"] == "https://new.example.com/feed"
    assert body["name"] == "New Feed"
    assert body["source_type"] == "rss"
    assert body["is_enabled"] is True
    assert body["article_count_24h"] == 0
    assert uuid.UUID(body["id"])


@pytest.mark.asyncio
async def test_create_source_defaults_name_to_empty_string(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/sources",
        json={"url": "https://noname.example.com/feed"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == ""


@pytest.mark.asyncio
async def test_create_source_trims_long_name(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/sources",
        json={"url": "https://longname.example.com/feed", "name": "x" * 300},
    )
    assert resp.status_code == 201
    assert len(resp.json()["name"]) == 200


@pytest.mark.asyncio
async def test_create_source_409_on_duplicate_url(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_source(session, url="https://dup.example.com/feed")
    resp = await client.post(
        "/api/v1/sources",
        json={"url": "https://dup.example.com/feed"},
    )
    assert resp.status_code == 409
    assert "sudah terdaftar" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_source_rejects_unknown_fields(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/sources",
        json={"url": "https://extra.example.com/feed", "hacked": True},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /sources — pg_notify behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_enabled_source_calls_pg_notify(client: AsyncClient) -> None:
    with patch("api.routes.sources.text", side_effect=real_text) as spy:
        resp = await client.post(
            "/api/v1/sources",
            json={"url": "https://notify-on.example.com/feed", "is_enabled": True},
        )
    assert resp.status_code == 201
    notify_calls = [c for c in spy.call_args_list if "pg_notify" in c.args[0]]
    assert len(notify_calls) == 1
    assert notify_calls[0].args[0] == "SELECT pg_notify('rss_source_created', :id)"


@pytest.mark.asyncio
async def test_create_disabled_source_skips_pg_notify(client: AsyncClient) -> None:
    with patch("api.routes.sources.text", side_effect=real_text) as spy:
        resp = await client.post(
            "/api/v1/sources",
            json={"url": "https://notify-off.example.com/feed", "is_enabled": False},
        )
    assert resp.status_code == 201
    notify_calls = [c for c in spy.call_args_list if "pg_notify" in c.args[0]]
    assert len(notify_calls) == 0


# ---------------------------------------------------------------------------
# DELETE /sources/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_source_returns_204(
    client: AsyncClient, session: AsyncSession
) -> None:
    source = await _seed_source(session, url="https://delete-me.example.com/feed")
    resp = await client.delete(f"/api/v1/sources/{source.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_source_404_on_missing(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/v1/sources/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_source_409_when_has_articles(
    client: AsyncClient, session: AsyncSession
) -> None:
    source = await _seed_source(session, url="https://has-articles.example.com/feed")
    await _seed_article(session, source.id)
    resp = await client.delete(f"/api/v1/sources/{source.id}")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# PATCH /sources/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_source_updates_is_enabled(
    client: AsyncClient, session: AsyncSession
) -> None:
    source = await _seed_source(
        session, url="https://patch-me.example.com/feed", is_enabled=True
    )
    resp = await client.patch(f"/api/v1/sources/{source.id}", json={"is_enabled": False})
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is False


@pytest.mark.asyncio
async def test_patch_source_404_on_missing(client: AsyncClient) -> None:
    resp = await client.patch(f"/api/v1/sources/{uuid.uuid4()}", json={"is_enabled": False})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_source_rejects_unknown_fields(
    client: AsyncClient, session: AsyncSession
) -> None:
    source = await _seed_source(session, url="https://patch-extra.example.com/feed")
    resp = await client.patch(
        f"/api/v1/sources/{source.id}", json={"is_enabled": False, "hacked": True}
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# article_count_24h semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_article_count_24h_excludes_older_articles(
    client: AsyncClient, session: AsyncSession
) -> None:
    source = await _seed_source(session, url="https://count.example.com/feed", name="Count")
    now = datetime.now(UTC).replace(tzinfo=None)
    fresh = Article(
        source_id=source.id,
        title="Fresh",
        url=f"https://count.example.com/fresh-{uuid.uuid4()}",
    )
    fresh.created_at = now - timedelta(hours=2)
    stale = Article(
        source_id=source.id,
        title="Stale",
        url=f"https://count.example.com/stale-{uuid.uuid4()}",
    )
    stale.created_at = now - timedelta(hours=48)
    session.add_all([fresh, stale])
    await session.flush()

    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["name"] == "Count")
    assert row["article_count_24h"] == 1


@pytest.mark.asyncio
async def test_status_and_last_fetched_at_round_trip(
    client: AsyncClient, session: AsyncSession
) -> None:
    fetched_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10)
    source = ContentSource(
        name="Status Source",
        url="https://status.example.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
        status=SourceStatus.active,
        last_fetched_at=fetched_at,
    )
    session.add(source)
    await session.flush()

    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["name"] == "Status Source")
    assert row["status"] == "active"
    assert row["last_fetched_at"] is not None
    parsed = datetime.fromisoformat(row["last_fetched_at"])
    assert parsed.replace(tzinfo=None, microsecond=0) == fetched_at.replace(microsecond=0)


@pytest.mark.asyncio
async def test_internal_source_type_listed(
    client: AsyncClient, session: AsyncSession
) -> None:
    source = ContentSource(
        name="Tempo Internal",
        url="https://internal.example.com/feed",
        source_type=SourceType.internal,
        is_enabled=True,
    )
    session.add(source)
    await session.flush()

    resp = await client.get("/api/v1/sources")
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["name"] == "Tempo Internal")
    assert row["source_type"] == "internal"


# ---------------------------------------------------------------------------
# pg_notify resilience: failure must not 500 the POST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_source_pg_notify_failure_returns_201(client: AsyncClient) -> None:
    def _exploding_text(stmt: str):
        if "pg_notify" in stmt:
            raise RuntimeError("simulated listener failure")
        return real_text(stmt)

    with patch("api.routes.sources.text", side_effect=_exploding_text):
        resp = await client.post(
            "/api/v1/sources",
            json={"url": "https://notify-fail.example.com/feed", "name": "NotifyFail"},
        )

    assert resp.status_code == 201
    assert resp.json()["url"] == "https://notify-fail.example.com/feed"


@pytest.mark.asyncio
async def test_patch_count_matches_list_count(
    client: AsyncClient, session: AsyncSession
) -> None:
    source = await _seed_source(
        session, url="https://consist.example.com/feed", name="Consist"
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    for i in range(3):
        a = Article(
            source_id=source.id,
            title=f"A{i}",
            url=f"https://consist.example.com/a-{i}-{uuid.uuid4()}",
        )
        a.created_at = now - timedelta(minutes=10 * i)
        session.add(a)
    await session.flush()

    list_resp = await client.get("/api/v1/sources")
    list_row = next(r for r in list_resp.json() if r["name"] == "Consist")
    patch_resp = await client.patch(
        f"/api/v1/sources/{source.id}", json={"is_enabled": True}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["article_count_24h"] == list_row["article_count_24h"] == 3
