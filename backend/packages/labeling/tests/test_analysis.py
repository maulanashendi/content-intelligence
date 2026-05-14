import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from labeling.analysis import _find_cached_claims, _load_cluster_articles, run


def _make_cluster(member_count=3):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.member_count = member_count
    return c


def _make_insight(cluster_id):
    i = MagicMock()
    i.cluster_id = cluster_id
    i.summary = None
    return i


def _make_session(clusters, articles, cached=None, insight=None):
    session = AsyncMock()

    # each execute() call returns a different result depending on call order;
    # use side_effect list to control sequential responses
    clusters_result = MagicMock()
    clusters_result.scalars.return_value.all.return_value = clusters

    articles_result = MagicMock()
    articles_result.all.return_value = articles

    cache_result = MagicMock()
    cache_result.one_or_none.return_value = cached

    insight_result = MagicMock()
    insight_result.scalar_one_or_none.return_value = insight

    session.execute.side_effect = [
        clusters_result,
        *(
            # for each article: one cache-check execute
            [cache_result] * len(articles)
        ),
        insight_result,
    ]
    return session


# ── _load_cluster_articles ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_cluster_articles_returns_rows():
    row = MagicMock()
    row.id = uuid.uuid4()
    row.title = "Judul"
    row.content = "Isi artikel."

    result = MagicMock()
    result.all.return_value = [row]

    session = AsyncMock()
    session.execute.return_value = result

    rows = await _load_cluster_articles(session, uuid.uuid4())
    assert len(rows) == 1
    assert rows[0] == (row.id, "Judul", "Isi artikel.")


@pytest.mark.asyncio
async def test_load_cluster_articles_handles_null_fields():
    row = MagicMock()
    row.id = uuid.uuid4()
    row.title = None
    row.content = None

    result = MagicMock()
    result.all.return_value = [row]

    session = AsyncMock()
    session.execute.return_value = result

    rows = await _load_cluster_articles(session, uuid.uuid4())
    assert rows[0] == (row.id, "", "")


# ── _find_cached_claims ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_cached_claims_returns_none_on_miss():
    result = MagicMock()
    result.one_or_none.return_value = None
    session = AsyncMock()
    session.execute.return_value = result

    assert await _find_cached_claims(session, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_find_cached_claims_returns_tuple_on_hit():
    row = MagicMock()
    row.main_entity = "BI"
    row.information_claims = ["Suku bunga turun", "Inflasi terkendali"]

    result = MagicMock()
    result.one_or_none.return_value = row
    session = AsyncMock()
    session.execute.return_value = result

    hit = await _find_cached_claims(session, uuid.uuid4())
    assert hit == ("BI", ["Suku bunga turun", "Inflasi terkendali"])


# ── run() ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_skips_cluster_with_no_articles():
    cluster = _make_cluster()

    with (
        patch("labeling.analysis.get_session") as mock_ctx,
        patch("labeling.analysis._load_cluster_articles", return_value=[]),
    ):
        session = AsyncMock()
        mock_ctx.return_value.__aenter__.return_value = session

        clusters_result = MagicMock()
        clusters_result.scalars.return_value.all.return_value = [cluster]
        session.execute.return_value = clusters_result

        result = await run()

    assert result["analyzed"] == 0
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_run_uses_cache_and_skips_llm():
    cluster = _make_cluster()
    article_id = uuid.uuid4()
    insight = _make_insight(cluster.id)

    with (
        patch("labeling.analysis.get_session") as mock_ctx,
        patch(
            "labeling.analysis._load_cluster_articles",
            return_value=[(article_id, "Judul", "Isi")],
        ),
        patch(
            "labeling.analysis._find_cached_claims",
            return_value=("BI", ["Fakta A"]),
        ),
        patch("labeling.analysis.deduplicate_claims", return_value=["Fakta A"]) as mock_dedup,
        patch("labeling.analysis.extract_article_claims") as mock_extract,
    ):
        session = AsyncMock()
        mock_ctx.return_value.__aenter__.return_value = session

        clusters_result = MagicMock()
        clusters_result.scalars.return_value.all.return_value = [cluster]

        insight_result = MagicMock()
        insight_result.scalar_one_or_none.return_value = insight

        # run() calls: 1) clusters SELECT, 2) insight SELECT (no UPDATE on cache hit)
        session.execute.side_effect = [clusters_result, insight_result]

        result = await run()

    mock_extract.assert_not_called()
    mock_dedup.assert_called_once_with([["Fakta A"]])
    assert insight.summary == ["Fakta A"]
    assert result["analyzed"] == 1
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_run_calls_llm_on_cache_miss():
    cluster = _make_cluster()
    article_id = uuid.uuid4()
    insight = _make_insight(cluster.id)

    with (
        patch("labeling.analysis.get_session") as mock_ctx,
        patch(
            "labeling.analysis._load_cluster_articles",
            return_value=[(article_id, "Judul", "Isi artikel panjang")],
        ),
        patch("labeling.analysis._find_cached_claims", return_value=None),
        patch(
            "labeling.analysis.extract_article_claims",
            return_value={"main_entity": "KPU", "information_claims": ["Pemilu selesai"]},
        ) as mock_extract,
        patch("labeling.analysis.deduplicate_claims", return_value=["Pemilu selesai"]),
    ):
        session = AsyncMock()
        mock_ctx.return_value.__aenter__.return_value = session

        clusters_result = MagicMock()
        clusters_result.scalars.return_value.all.return_value = [cluster]

        update_result = MagicMock()  # UPDATE Article

        insight_result = MagicMock()
        insight_result.scalar_one_or_none.return_value = insight

        # run() calls: 1) clusters SELECT, 2) UPDATE Article, 3) insight SELECT
        session.execute.side_effect = [clusters_result, update_result, insight_result]

        result = await run()

    mock_extract.assert_called_once_with("Judul", "Isi artikel panjang")
    assert insight.summary == ["Pemilu selesai"]
    assert result["analyzed"] == 1


@pytest.mark.asyncio
async def test_run_skips_cluster_on_llm_error():
    cluster = _make_cluster()
    article_id = uuid.uuid4()

    with (
        patch("labeling.analysis.get_session") as mock_ctx,
        patch(
            "labeling.analysis._load_cluster_articles",
            return_value=[(article_id, "Judul", "Isi")],
        ),
        patch("labeling.analysis._find_cached_claims", return_value=None),
        patch("labeling.analysis.extract_article_claims", side_effect=RuntimeError("OOM")),
    ):
        session = AsyncMock()
        mock_ctx.return_value.__aenter__.return_value = session

        clusters_result = MagicMock()
        clusters_result.scalars.return_value.all.return_value = [cluster]
        session.execute.return_value = clusters_result

        result = await run()

    assert result["analyzed"] == 0
    assert result["skipped"] == 1
