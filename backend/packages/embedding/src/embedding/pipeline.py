import asyncio
import logging

import numpy as np
from core.config import settings
from core.db import get_session
from core.models import Article, ArticleEmbedding
from llm.embeddings import build_embedding_client
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
    from llm.providers import attribution_headers

    texts = [t[: settings.embedding_max_input_chars] for t in texts]

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


async def _encode_resilient(texts: list[str]) -> list[np.ndarray | None]:
    """Embed a batch; on batch failure fall back to per-item so one bad input cannot
    drop the whole batch. Returns one vector per input, None where embedding failed."""
    try:
        vectors = await _encode(texts)
        return [np.asarray(v, dtype=np.float32) for v in vectors]
    except Exception as exc:  # network/API boundary — degrade to per-item
        logger.warning("batch embed failed; retrying per-item", extra={"size": len(texts), "error": str(exc)})
    results: list[np.ndarray | None] = []
    for text in texts:
        try:
            vectors = await _encode([text])
            results.append(np.asarray(vectors[0], dtype=np.float32))
        except Exception as exc:
            logger.warning("per-item embed failed; skipping article", extra={"error": str(exc)})
            results.append(None)
    return results


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
            vectors = await _encode_resilient(texts)
            saved = 0
            for (article_id, _, _, _), vector in zip(rows, vectors, strict=True):
                if vector is None:
                    continue
                if vector.shape[0] != 768:
                    raise ValueError(f"embedding dim mismatch: got {vector.shape[0]}, expected 768")
                session.add(
                    ArticleEmbedding(
                        article_id=article_id,
                        model_name=model_name,
                        model_version=settings.embedding_model_version or None,
                        embedding=vector.tolist(),
                    )
                )
                saved += 1

            await session.commit()
            total += saved
            logger.info("embedded batch", extra={"count": saved, "skipped": len(rows) - saved, "total": total})

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
