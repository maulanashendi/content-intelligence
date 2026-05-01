import math
import uuid
from datetime import UTC, datetime, timedelta

from core.models import Article, ContentSource, SourceType
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _source(source_type: SourceType = SourceType.rss, *, name: str = "Test Source") -> ContentSource:
    return ContentSource(
        id=uuid.uuid4(),
        name=name,
        url=f"https://test-{uuid.uuid4()}.com/rss",
        source_type=source_type,
    )


def _article(
    source_id: uuid.UUID,
    *,
    title: str = "Test Article",
    first_paragraph: str | None = None,
    published_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Article:
    a = Article(
        id=uuid.uuid4(),
        source_id=source_id,
        title=title,
        url=f"https://test-{uuid.uuid4()}.com/article",
        first_paragraph=first_paragraph,
        published_at=published_at,
    )
    if created_at is not None:
        a.created_at = created_at
    return a


async def _all_items(client: AsyncClient) -> list[dict]:
    """Fetch all articles across pages (up to 1000) for ID-based lookup."""
    resp = await client.get("/api/v1/articles?page=1&page_size=100")
    data = resp.json()
    items = list(data["items"])
    total_pages = data["total_pages"]
    for p in range(2, min(total_pages + 1, 11)):
        resp = await client.get(f"/api/v1/articles?page={p}&page_size=100")
        items.extend(resp.json()["items"])
    return items


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


async def test_list_articles_response_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    assert data["page"] == 1
    assert data["page_size"] == 20


async def test_list_articles_total_pages_consistent(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles?page_size=5")
    assert response.status_code == 200
    data = response.json()
    expected_pages = math.ceil(data["total"] / 5) if data["total"] else 1
    assert data["total_pages"] == expected_pages


# ---------------------------------------------------------------------------
# Field values
# ---------------------------------------------------------------------------


async def test_list_articles_returns_correct_fields(session: AsyncSession, client: AsyncClient) -> None:
    source = _source(name="Kompas RSS")
    article = Article(
        id=uuid.uuid4(),
        source_id=source.id,
        title="BBM Naik per Mei 2025",
        url="https://kompas.com/read/2025/05/bbm-naik",
        first_paragraph="Pertamina menaikkan harga.",
        published_at=_NOW - timedelta(hours=2),
    )
    session.add_all([source, article])
    await session.flush()

    items = await _all_items(client)
    item = next((i for i in items if i["id"] == str(article.id)), None)
    assert item is not None
    assert item["title"] == "BBM Naik per Mei 2025"
    assert item["url"] == "https://kompas.com/read/2025/05/bbm-naik"
    assert item["first_paragraph"] == "Pertamina menaikkan harga."
    assert item["source_name"] == "Kompas RSS"
    assert item["source_type"] == "rss"
    assert item["published_at"] is not None
    assert item["created_at"] is not None


async def test_list_articles_null_first_paragraph_and_published_at(
    session: AsyncSession, client: AsyncClient
) -> None:
    source = _source()
    article = _article(source.id, title="No Para Article")
    session.add_all([source, article])
    await session.flush()

    items = await _all_items(client)
    item = next((i for i in items if i["id"] == str(article.id)), None)
    assert item is not None
    assert item["first_paragraph"] is None
    assert item["published_at"] is None


# ---------------------------------------------------------------------------
# source_type propagation
# ---------------------------------------------------------------------------


async def test_list_articles_source_type_rss(session: AsyncSession, client: AsyncClient) -> None:
    source = _source(SourceType.rss, name="Kompas")
    article = _article(source.id, title="RSS Article Unique")
    session.add_all([source, article])
    await session.flush()

    items = await _all_items(client)
    item = next((i for i in items if i["id"] == str(article.id)), None)
    assert item is not None
    assert item["source_type"] == "rss"


async def test_list_articles_source_type_internal(session: AsyncSession, client: AsyncClient) -> None:
    source = _source(SourceType.internal, name="Tempo Internal")
    article = _article(source.id, title="Internal Article Unique")
    session.add_all([source, article])
    await session.flush()

    items = await _all_items(client)
    item = next((i for i in items if i["id"] == str(article.id)), None)
    assert item is not None
    assert item["source_type"] == "internal"


# ---------------------------------------------------------------------------
# Ordering: most recently ingested first
# ---------------------------------------------------------------------------


async def test_list_articles_ordered_by_created_at_desc(
    session: AsyncSession, client: AsyncClient
) -> None:
    source = _source()
    older = _article(source.id, title="Older Article", created_at=_NOW - timedelta(hours=2))
    newer = _article(source.id, title="Newer Article", created_at=_NOW - timedelta(minutes=30))
    session.add_all([source, older, newer])
    await session.flush()

    items = await _all_items(client)
    ids = [i["id"] for i in items]
    older_pos = ids.index(str(older.id))
    newer_pos = ids.index(str(newer.id))
    assert newer_pos < older_pos, "Newer article should appear before older article"


# ---------------------------------------------------------------------------
# Pagination contract
# ---------------------------------------------------------------------------


async def test_list_articles_page_size_respected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 5
    assert data["page_size"] == 5


async def test_list_articles_page_2_offset(client: AsyncClient) -> None:
    resp1 = await client.get("/api/v1/articles?page=1&page_size=3")
    resp2 = await client.get("/api/v1/articles?page=2&page_size=3")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    ids1 = {i["id"] for i in resp1.json()["items"]}
    ids2 = {i["id"] for i in resp2.json()["items"]}
    assert ids1.isdisjoint(ids2), "Page 1 and page 2 must not overlap"


async def test_list_articles_beyond_last_page_returns_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles?page=99999&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["page"] == 99999


async def test_list_articles_default_page_size_is_20(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles")
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 20
    assert len(data["items"]) <= 20


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


async def test_list_articles_invalid_page_zero(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles?page=0")
    assert response.status_code == 422


async def test_list_articles_page_size_too_large(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles?page_size=101")
    assert response.status_code == 422


async def test_list_articles_negative_page_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles?page=-1")
    assert response.status_code == 422


async def test_list_articles_non_numeric_page_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles?page=abc")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Envelope shape: empty DB and exact field set
# ---------------------------------------------------------------------------


async def test_list_articles_empty_returns_zero_total_one_page(client: AsyncClient) -> None:
    response = await client.get("/api/v1/articles")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["total_pages"] == 1


async def test_list_articles_item_has_exact_field_set(
    session: AsyncSession, client: AsyncClient
) -> None:
    source = _source(name="Field Shape Source")
    article = Article(
        id=uuid.uuid4(),
        source_id=source.id,
        title="Field Shape Article",
        url=f"https://shape-{uuid.uuid4()}.com/article",
        first_paragraph="Body.",
        published_at=_NOW - timedelta(hours=1),
    )
    session.add_all([source, article])
    await session.flush()

    items = await _all_items(client)
    item = next(i for i in items if i["id"] == str(article.id))
    expected = {
        "id",
        "title",
        "url",
        "first_paragraph",
        "published_at",
        "created_at",
        "source_name",
        "source_type",
    }
    assert set(item.keys()) == expected


async def test_list_articles_published_at_serializes_iso8601(
    session: AsyncSession, client: AsyncClient
) -> None:
    source = _source()
    pub = _NOW - timedelta(hours=3)
    article = _article(source.id, title="ISO8601 Article", published_at=pub)
    session.add_all([source, article])
    await session.flush()

    items = await _all_items(client)
    item = next(i for i in items if i["id"] == str(article.id))
    assert item["published_at"] is not None
    parsed = datetime.fromisoformat(item["published_at"])
    assert parsed.replace(tzinfo=None) == pub.replace(microsecond=parsed.microsecond)


async def test_list_articles_join_multiple_sources_distinct_names(
    session: AsyncSession, client: AsyncClient
) -> None:
    src_a = _source(name="Source A")
    src_b = _source(name="Source B")
    art_a = _article(src_a.id, title="A Article")
    art_b = _article(src_b.id, title="B Article")
    session.add_all([src_a, src_b, art_a, art_b])
    await session.flush()

    items = await _all_items(client)
    item_a = next(i for i in items if i["id"] == str(art_a.id))
    item_b = next(i for i in items if i["id"] == str(art_b.id))
    assert item_a["source_name"] == "Source A"
    assert item_b["source_name"] == "Source B"
