import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from core.config import settings
from core.models import Article, ArticleEmbedding, ContentSource, SourceType
from embedding.pipeline import _encode_api, _encode_resilient, run
from sqlalchemy import select


async def _seed_source(session):
    source = ContentSource(
        name="test-src",
        url=f"http://example-{uuid.uuid4()}.com",
        source_type=SourceType.rss,
    )
    session.add(source)
    await session.flush()
    return source


async def _seed_article(session, source_id):
    article = Article(
        source_id=source_id,
        title="Economy headline",
        url=f"http://example-{uuid.uuid4()}.com/article",
    )
    session.add(article)
    await session.flush()
    return article


def _make_embedder():
    mock = MagicMock()

    def fake_encode(texts, **kwargs):
        return np.zeros((len(texts), 768), dtype=np.float32)

    mock.encode.side_effect = fake_encode
    return mock


@asynccontextmanager
async def _session_cm(db_session):
    yield db_session


@pytest.mark.asyncio
async def test_run_embeds_unembedded_articles_local(db_session, monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "local")
    source = await _seed_source(db_session)
    article = await _seed_article(db_session, source.id)

    with (
        patch("embedding.embedder.get_embedder", return_value=_make_embedder()),
        patch("embedding.pipeline.get_session", lambda: _session_cm(db_session)),
    ):
        count = await run()

    assert count == 1
    rows = (
        (await db_session.execute(
            select(ArticleEmbedding).where(ArticleEmbedding.article_id == article.id)
        )).scalars().all()
    )
    assert len(rows) == 1
    assert rows[0].model_name == "google/embeddinggemma-300m"


@pytest.mark.asyncio
async def test_run_is_noop_when_all_embedded_local(db_session):
    source = await _seed_source(db_session)
    article = await _seed_article(db_session, source.id)
    db_session.add(
        ArticleEmbedding(
            article_id=article.id,
            model_name="google/embeddinggemma-300m",
            embedding=[0.0] * 768,
        )
    )
    await db_session.flush()

    mock_embedder = _make_embedder()
    with (
        patch("embedding.embedder.get_embedder", return_value=mock_embedder),
        patch("embedding.pipeline.get_session", lambda: _session_cm(db_session)),
    ):
        count = await run()

    assert count == 0
    mock_embedder.encode.assert_not_called()


@pytest.mark.asyncio
async def test_run_api_path_uses_embedding_client_and_normalizes(db_session, monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "api")
    monkeypatch.setattr(settings, "embedding_api_model", "openai/text-embedding-3-large")
    source = await _seed_source(db_session)
    article = await _seed_article(db_session, source.id)

    mock_client = MagicMock()

    async def fake_embed(texts, *, model, dimensions):
        assert model == "openai/text-embedding-3-large"
        assert dimensions == 768
        # un-normalized vector [3, 4, 0...]: norm 5 -> expect [0.6, 0.8, 0...]
        return [[3.0, 4.0] + [0.0] * 766 for _ in texts]

    mock_client.embed = fake_embed
    get_embedder_spy = MagicMock()

    with (
        patch("embedding.pipeline.build_embedding_client", return_value=mock_client),
        patch("embedding.embedder.get_embedder", get_embedder_spy),
        patch("embedding.pipeline.get_session", lambda: _session_cm(db_session)),
    ):
        count = await run()

    assert count == 1
    get_embedder_spy.assert_not_called()  # api path must not touch the local embedder
    rows = (
        (await db_session.execute(
            select(ArticleEmbedding).where(ArticleEmbedding.article_id == article.id)
        )).scalars().all()
    )
    assert rows[0].model_name == "openai/text-embedding-3-large"
    assert abs(rows[0].embedding[0] - 0.6) < 1e-6
    assert abs(rows[0].embedding[1] - 0.8) < 1e-6


@pytest.mark.asyncio
async def test_reembed_clears_non_target_then_recomputes(db_session, monkeypatch):
    from embedding.pipeline import reembed

    monkeypatch.setattr(settings, "embedding_provider", "api")
    monkeypatch.setattr(settings, "embedding_api_model", "openai/text-embedding-3-large")
    source = await _seed_source(db_session)
    stale = await _seed_article(db_session, source.id)
    keep = await _seed_article(db_session, source.id)
    db_session.add_all(
        [
            ArticleEmbedding(
                article_id=stale.id,
                model_name="google/embeddinggemma-300m",
                embedding=[0.0] * 768,
            ),
            ArticleEmbedding(
                article_id=keep.id,
                model_name="openai/text-embedding-3-large",
                embedding=[0.0] * 768,
            ),
        ]
    )
    await db_session.flush()

    mock_client = MagicMock()

    async def fake_embed(texts, *, model, dimensions):
        return [[1.0] + [0.0] * 767 for _ in texts]

    mock_client.embed = fake_embed

    with (
        patch("embedding.pipeline.build_embedding_client", return_value=mock_client),
        patch("embedding.pipeline.get_session", lambda: _session_cm(db_session)),
    ):
        result = await reembed()

    assert result["deleted"] == 1
    assert result["embedded"] == 1  # only the stale article re-embedded; keep was skipped
    rows = (await db_session.execute(select(ArticleEmbedding))).scalars().all()
    assert len(rows) == 2
    assert {r.model_name for r in rows} == {"openai/text-embedding-3-large"}


# ---------------------------------------------------------------------------
# Part 1: input truncation in _encode_api
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_encode_api_truncates_texts_to_max_input_chars(monkeypatch):
    """_encode_api must truncate each text to embedding_max_input_chars before
    calling the embedding client so a single long article cannot exceed the model
    token limit and fail the whole batch."""
    monkeypatch.setattr(settings, "embedding_provider", "api")
    monkeypatch.setattr(settings, "embedding_max_input_chars", 10)

    captured: list[list[str]] = []

    async def fake_embed(texts, *, model, dimensions):
        captured.append(list(texts))
        n = len(texts)
        return [[1.0] + [0.0] * 767 for _ in range(n)]

    mock_client = MagicMock()
    mock_client.embed = fake_embed

    with patch("embedding.pipeline.build_embedding_client", return_value=mock_client):
        await _encode_api(["short", "this is a very long text that exceeds the limit"])

    assert captured, "embed() was never called"
    sent = captured[0]
    assert all(len(t) <= 10 for t in sent), f"texts not truncated: {sent}"
    assert sent[0] == "short"
    assert sent[1] == "this is a "


# ---------------------------------------------------------------------------
# Part 2: _encode_resilient falls back to per-item on batch failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_encode_resilient_falls_back_per_item_on_batch_error(monkeypatch):
    """When _encode raises on a batch of >1 texts, _encode_resilient retries each
    text individually so the whole batch is NOT dropped."""
    monkeypatch.setattr(settings, "embedding_provider", "api")

    async def fake_encode(texts: list[str]):
        if len(texts) > 1:
            raise ValueError("No embedding data received")
        return np.zeros((1, 768), dtype=np.float32)

    with patch("embedding.pipeline._encode", side_effect=fake_encode):
        results = await _encode_resilient(["text1", "text2", "text3"])

    assert len(results) == 3
    assert all(v is not None for v in results)
    assert all(v.shape == (768,) for v in results)


# ---------------------------------------------------------------------------
# Part 3: _encode_resilient marks bad items None and keeps the rest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_encode_resilient_marks_persistently_bad_items_none(monkeypatch):
    """When per-item retry also fails for a specific text, _encode_resilient returns
    None for that index and keeps the successful neighbours non-None."""
    monkeypatch.setattr(settings, "embedding_provider", "api")

    bad_text = "bad-article"

    async def fake_encode(texts: list[str]):
        if len(texts) > 1:
            raise ValueError("batch error")
        if texts[0] == bad_text:
            raise ValueError("per-item error for bad article")
        return np.zeros((1, 768), dtype=np.float32)

    with patch("embedding.pipeline._encode", side_effect=fake_encode):
        results = await _encode_resilient(["text1", bad_text, "text3"])

    assert len(results) == 3
    assert results[0] is not None
    assert results[1] is None  # bad article is skipped
    assert results[2] is not None
