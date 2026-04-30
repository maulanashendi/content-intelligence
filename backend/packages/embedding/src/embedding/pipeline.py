import logging

from core.config import settings
from core.db import get_session
from core.models import Article, ArticleEmbedding
from sqlalchemy import exists, select

from embedding.embedder import get_embedder

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


async def run() -> int:
    embedder = get_embedder()
    total = 0

    async with get_session() as session:
        while True:
            subq = select(ArticleEmbedding.article_id).where(
                ArticleEmbedding.article_id == Article.id
            )
            result = await session.execute(
                select(Article.id, Article.title, Article.first_paragraph)
                .where(~exists(subq))
                .limit(BATCH_SIZE)
            )
            rows = result.all()
            if not rows:
                break

            texts = [
                f"{title}\n{first_paragraph}" if first_paragraph else title
                for _, title, first_paragraph in rows
            ]
            vectors = embedder.encode(texts, normalize_embeddings=True)
            if vectors.shape[1] != 768:
                raise ValueError(f"embedding dim mismatch: got {vectors.shape[1]}, expected 768")

            for (article_id, _, _), vector in zip(rows, vectors, strict=True):
                session.add(
                    ArticleEmbedding(
                        article_id=article_id,
                        model_name=settings.embedding_model_name,
                        model_version=settings.embedding_model_version or None,
                        embedding=vector.tolist(),
                    )
                )

            await session.commit()
            total += len(rows)
            logger.info("embedded batch", extra={"count": len(rows), "total": total})

    return total
