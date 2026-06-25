"""SP3 pre-cutover embedding quality gate. NON-DESTRUCTIVE: never writes article_embedding.

Embeds the live (already-embedded) article set with each candidate API model,
runs the production UMAP->HDBSCAN, and logs cluster-quality signals + sample
cluster titles for a human go/no-go before the irreversible reembed.

Run (host venv, EMBEDDING_API_KEY set in backend/.env):
    cd backend && ./.venv/bin/python scripts/validate_embeddings.py
"""
import asyncio
import logging

import numpy as np
from clustering.clusterer import cluster as hdbscan_cluster
from clustering.quality import cluster_quality_signals
from clustering.reducer import reduce as umap_reduce
from core.config import settings
from core.db import get_session
from core.logging import configure_logging
from core.models import Article, ArticleEmbedding
from llm.embeddings import build_embedding_client
from sqlalchemy import select

logger = logging.getLogger(__name__)

CANDIDATES = ["openai/text-embedding-3-large", "google/gemini-embedding-001"]
SAMPLE_LIMIT = 8000
EMBED_BATCH = 256


async def _load_sample() -> tuple[list[str], list[str]]:
    async with get_session() as session:
        result = await session.execute(
            select(Article.title, Article.first_paragraph, Article.content)
            .join(ArticleEmbedding, ArticleEmbedding.article_id == Article.id)
            .limit(SAMPLE_LIMIT)
        )
        rows = result.all()
    titles = [title for title, _, _ in rows]
    texts = [
        f"{title}\n{body}" if (body := (content or first_paragraph)) else title
        for title, first_paragraph, content in rows
    ]
    return titles, texts


async def _embed_all(model: str, texts: list[str]) -> np.ndarray:
    client = build_embedding_client(
        settings.embedding_api_key,
        settings.embedding_api_base_url,
        settings.embedding_request_timeout_seconds,
    )
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        out.extend(await client.embed(texts[i : i + EMBED_BATCH], model=model, dimensions=768))
    vectors = np.asarray(out, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


async def main() -> None:
    configure_logging(settings.log_level)
    titles, texts = await _load_sample()
    logger.info("validation sample loaded", extra={"n": len(texts)})

    for model in CANDIDATES:
        vectors = await _embed_all(model, texts)
        reduced = umap_reduce(vectors)
        labels, _ = hdbscan_cluster(reduced)
        signals = cluster_quality_signals(labels)
        logger.info(
            "candidate signals",
            extra={"model": model, "returned_dims": int(vectors.shape[1]), **signals},
        )
        for cid in sorted(set(labels.tolist()) - {-1})[:5]:
            members = [titles[i] for i in range(len(titles)) if labels[i] == cid][:6]
            logger.info("sample cluster", extra={"model": model, "cluster": int(cid), "titles": members})


if __name__ == "__main__":
    asyncio.run(main())
