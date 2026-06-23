import uuid

import core.db as _core_db
import numpy as np
import pytest
import pytest_asyncio
from core.config import settings
from core.db import get_session
from core.models import ContentSource, SourceType
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

EMBEDDING_DIM = 768
NUM_CLUSTERS = 3
ARTICLES_PER_CLUSTER = 6


@pytest.fixture
def fake_embedder() -> object:
    """Sentence-transformers-shaped stub for deterministic clustering.

    Articles prefixed with `<cluster_idx>|` map to orthogonal axis-aligned
    vectors so UMAP+HDBSCAN recovers clusters deterministically.
    """
    rng = np.random.default_rng(seed=42)

    class _Embedder:
        def encode(self, texts, normalize_embeddings: bool = True, **_: object) -> np.ndarray:
            vectors = np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)
            for i, raw in enumerate(texts):
                cluster_idx = int(raw.split("|", 1)[0])
                vectors[i, cluster_idx % NUM_CLUSTERS] = 1.0
                vectors[i] += rng.normal(scale=0.005, size=EMBEDDING_DIM).astype(np.float32)
            if normalize_embeddings:
                norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                vectors = vectors / norms
            return vectors

    return _Embedder()

E2E_TABLES = (
    "cluster_insight",
    "article_cluster_member",
    "article_cluster",
    "cluster_run_stage",
    "cluster_run",
    "article_embedding",
    "article_gsc_metric",
    "trend_signal_article",
    "trend_signal",
    "article",
    "content_source",
)


@pytest_asyncio.fixture
async def clean_db():
    # Use NullPool and rebind core.db so get_session() inside pipeline code
    # does not pull connections from a previous test's event loop.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    _core_db._engine = engine
    _core_db._session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            for table in E2E_TABLES:
                await conn.execute(text(f"DELETE FROM {table}"))
        yield
    finally:
        async with engine.begin() as conn:
            for table in E2E_TABLES:
                await conn.execute(text(f"DELETE FROM {table}"))
        await engine.dispose()


@pytest_asyncio.fixture
async def rss_source(clean_db) -> ContentSource:
    source = ContentSource(
        id=uuid.uuid4(),
        name="Fake RSS",
        url="https://fake.example.com/feed",
        source_type=SourceType.rss,
        is_enabled=True,
    )
    async with get_session() as session:
        session.add(source)
        await session.commit()
        await session.refresh(source)
    return source
