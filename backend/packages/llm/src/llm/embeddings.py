from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI


class EmbeddingClient(Protocol):
    async def embed(
        self, texts: list[str], *, model: str, dimensions: int | None = None
    ) -> list[list[float]]: ...


class OpenAICompatibleEmbeddingClient:
    def __init__(self, raw_client: AsyncOpenAI) -> None:
        self._client = raw_client

    async def embed(
        self, texts: list[str], *, model: str, dimensions: int | None = None
    ) -> list[list[float]]:
        kwargs: dict = {"model": model, "input": texts}
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        response = await self._client.embeddings.create(**kwargs)
        return [item.embedding for item in response.data]


@lru_cache(maxsize=4)
def build_embedding_client(
    api_key: str,
    base_url: str,
    timeout: float,
    headers: tuple[tuple[str, str], ...] = (),
) -> OpenAICompatibleEmbeddingClient:
    raw = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key or "not-needed",
        timeout=timeout,
        # openai SDK treats an empty dict the same as no headers; None is the correct sentinel
        default_headers=dict(headers) or None,
    )
    return OpenAICompatibleEmbeddingClient(raw)
