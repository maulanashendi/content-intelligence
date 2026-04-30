import uuid
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy import select

from core.models import Article, ArticleEmbedding, ContentSource, SourceType
from embedding.pipeline import run


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


@pytest.mark.asyncio
async def test_run_embeds_unembedded_articles(db_session):
    source = await _seed_source(db_session)
    article = await _seed_article(db_session, source.id)

    fake_vectors = np.zeros((1, 768), dtype=np.float32)
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = fake_vectors

    @asynccontextmanager
    async def mock_get_session():
        yield db_session

    with (
        patch("embedding.pipeline.get_embedder", return_value=mock_embedder),
        patch("embedding.pipeline.get_session", mock_get_session),
    ):
        count = await run()

    assert count == 1
    rows = (
        await db_session.execute(
            select(ArticleEmbedding).where(ArticleEmbedding.article_id == article.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].model_name == "google/embeddinggemma-300m"


@pytest.mark.asyncio
async def test_run_is_noop_when_all_embedded(db_session):
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

    mock_embedder = MagicMock()

    @asynccontextmanager
    async def mock_get_session():
        yield db_session

    with (
        patch("embedding.pipeline.get_embedder", return_value=mock_embedder),
        patch("embedding.pipeline.get_session", mock_get_session),
    ):
        count = await run()

    assert count == 0
    mock_embedder.encode.assert_not_called()
