from unittest.mock import AsyncMock, MagicMock

from llm.embeddings import OpenAICompatibleEmbeddingClient, build_embedding_client


def _make_raw_client(vectors: list[list[float]]) -> MagicMock:
    raw = MagicMock()
    response = MagicMock()
    response.data = [MagicMock(embedding=v) for v in vectors]
    raw.embeddings.create = AsyncMock(return_value=response)
    return raw


async def test_embed_returns_vectors_in_order():
    raw = _make_raw_client([[0.1, 0.2], [0.3, 0.4]])
    client = OpenAICompatibleEmbeddingClient(raw)
    out = await client.embed(["a", "b"], model="m", dimensions=768)
    assert out == [[0.1, 0.2], [0.3, 0.4]]


async def test_embed_passes_dimensions_when_set():
    raw = _make_raw_client([[0.0]])
    client = OpenAICompatibleEmbeddingClient(raw)
    await client.embed(["a"], model="m", dimensions=768)
    _, kwargs = raw.embeddings.create.call_args
    assert kwargs["dimensions"] == 768
    assert kwargs["model"] == "m"
    assert kwargs["input"] == ["a"]


async def test_embed_omits_dimensions_when_none():
    raw = _make_raw_client([[0.0]])
    client = OpenAICompatibleEmbeddingClient(raw)
    await client.embed(["a"], model="m", dimensions=None)
    _, kwargs = raw.embeddings.create.call_args
    assert "dimensions" not in kwargs


def test_build_embedding_client_caches():
    a = build_embedding_client("k", "https://openrouter.ai/api/v1", 60.0)
    b = build_embedding_client("k", "https://openrouter.ai/api/v1", 60.0)
    assert a is b
