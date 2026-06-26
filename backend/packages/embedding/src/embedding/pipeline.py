import asyncio
import logging

import numpy as np
from core.config import settings
from core.db import get_session
from core.models import Article, ArticleEmbedding
from sqlalchemy import delete, exists, select

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _active_model_name() -> str:
    if settings.embedding_provider == "api":
        return settings.embedding_api_model
    return settings.embedding_model_name


def _encode_local(texts: list[str]) -> np.ndarray:
    try:
        from embedding.embedder import get_embedder
    except ImportError as exc:
        raise RuntimeError(
            "EMBEDDING_PROVIDER=local but the local extra is not installed "
            "(torch/sentence-transformers missing). Deploy the pipeline-local "
            "image or set EMBEDDING_PROVIDER=api."
        ) from exc

    embedder = get_embedder()
    return embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)


async def _encode_api(texts: list[str]) -> np.ndarray:
    from llm.embeddings import build_embedding_client
    from llm.providers import attribution_headers

    client = build_embedding_client(
        settings.embedding_api_key,
        settings.embedding_api_base_url,
        settings.embedding_request_timeout_seconds,
        attribution_headers(
            settings.embedding_attribution_referer,
            settings.embedding_attribution_title,
        ),
    )
    raw = await client.embed(
        texts,
        model=settings.embedding_api_model,
        dimensions=settings.embedding_api_dimensions,
    )
    return _l2_normalize(np.asarray(raw, dtype=np.float32))


async def _encode(texts: list[str]) -> np.ndarray:
    if settings.embedding_provider == "api":
        return await _encode_api(texts)
    return await asyncio.to_thread(_encode_local, texts)


async def run() -> int:
    model_name = _active_model_name()
    total = 0

    async with get_session() as session:
        while True:
            subq = select(ArticleEmbedding.article_id).where(
                ArticleEmbedding.article_id == Article.id
            )
            result = await session.execute(
                select(Article.id, Article.title, Article.first_paragraph, Article.content)
                .where(~exists(subq))
                .limit(BATCH_SIZE)
            )
            rows = result.all()
            if not rows:
                break

            texts = [
                f"{title}\n{body}" if (body := (content or first_paragraph)) else title
                for _, title, first_paragraph, content in rows
            ]
            vectors = await _encode(texts)
            if vectors.shape[1] != 768:
                raise ValueError(f"embedding dim mismatch: got {vectors.shape[1]}, expected 768")

            for (article_id, _, _, _), vector in zip(rows, vectors, strict=True):
                session.add(
                    ArticleEmbedding(
                        article_id=article_id,
                        model_name=model_name,
                        model_version=settings.embedding_model_version or None,
                        embedding=vector.tolist(),
                    )
                )

            await session.commit()
            total += len(rows)
            logger.info("embedded batch", extra={"count": len(rows), "total": total})

    return total


async def reembed() -> dict[str, int]:
    """Operator-gated migration: drop embeddings not from the active model, then
    re-embed every now-unembedded article via run(). Resumable (run()'s ~exists
    guard skips already-migrated rows)."""
    model_name = _active_model_name()
    async with get_session() as session:
        result = await session.execute(
            delete(ArticleEmbedding).where(ArticleEmbedding.model_name != model_name)
        )
        await session.commit()
        deleted = result.rowcount or 0
    logger.info("reembed cleared stale embeddings", extra={"deleted": deleted, "model": model_name})
    embedded = await run()
    return {"deleted": deleted, "embedded": embedded}
