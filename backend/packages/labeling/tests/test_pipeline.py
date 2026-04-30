import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from labeling.pipeline import _get_top_articles, _load_current_clusters, run


def _make_cluster(cluster_id=None, member_count=5, label=None):
    cluster = MagicMock()
    cluster.id = cluster_id or uuid.uuid4()
    cluster.member_count = member_count
    cluster.label = label
    return cluster


@pytest.mark.asyncio
async def test_load_current_clusters():
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        _make_cluster(),
        _make_cluster(),
    ]

    session = AsyncMock()
    session.execute.return_value = mock_result

    clusters = await _load_current_clusters(session)
    assert len(clusters) == 2


@pytest.mark.asyncio
async def test_get_top_articles():
    row1 = MagicMock()
    row1.title = "Harga beras naik"
    row1.first_paragraph = "Melonjak tajam."

    mock_result = MagicMock()
    mock_result.all.return_value = [row1]

    session = AsyncMock()
    session.execute.return_value = mock_result

    articles = await _get_top_articles(session, uuid.uuid4())
    assert len(articles) == 1
    assert articles[0]["title"] == "Harga beras naik"


@pytest.mark.asyncio
async def test_labels_current_clusters():
    cluster_one = _make_cluster()
    cluster_two = _make_cluster()

    with (
        patch("labeling.pipeline.get_session") as mock_session_ctx,
        patch("labeling.pipeline._load_current_clusters", return_value=[cluster_one, cluster_two]),
        patch("labeling.pipeline._get_top_articles") as mock_get_articles,
        patch(
            "labeling.pipeline.generate_label",
            side_effect=["Lonjakan harga beras", "Harga gula ikut naik"],
        ),
    ):
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        mock_get_articles.return_value = [
            {"title": "Harga beras naik", "first_paragraph": "Melonjak."},
        ]

        result = await run()

    assert result["labeled"] == 2
    assert result["skipped"] == 0
    assert cluster_one.label == "Lonjakan harga beras"
    assert cluster_two.label == "Harga gula ikut naik"


@pytest.mark.asyncio
async def test_skips_non_current_clusters():
    non_current_cluster = _make_cluster(label=None)

    with (
        patch("labeling.pipeline.get_session") as mock_session_ctx,
        patch("labeling.pipeline._load_current_clusters", return_value=[]),
    ):
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session

        result = await run()

    assert result["labeled"] == 0
    assert result["skipped"] == 0
    assert non_current_cluster.label is None


@pytest.mark.asyncio
async def test_skips_cluster_on_llm_error():
    cluster = _make_cluster()

    with (
        patch("labeling.pipeline.get_session") as mock_session_ctx,
        patch("labeling.pipeline._load_current_clusters", return_value=[cluster]),
        patch("labeling.pipeline._get_top_articles") as mock_get_articles,
        patch("labeling.pipeline.generate_label", side_effect=RuntimeError("OOM")),
    ):
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        mock_get_articles.return_value = [
            {"title": "Test", "first_paragraph": "Test"},
        ]

        result = await run()

    assert result["labeled"] == 0
    assert result["skipped"] == 1
