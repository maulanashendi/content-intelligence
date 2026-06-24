import pytest
from pydantic import BaseModel

from llm.structured import complete_structured


class _Out(BaseModel):
    reply: str


class FakeLLMClient:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[dict] = []

    async def complete(self, *, model: str, messages: list[dict]) -> str:
        self.calls.append({"model": model, "messages": messages})
        return self._contents[len(self.calls) - 1]


async def test_parses_valid_json() -> None:
    client = FakeLLMClient(['{"reply":"pong"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], _Out)
    assert result.reply == "pong"


async def test_strips_code_fences() -> None:
    client = FakeLLMClient(['```json\n{"reply":"pong"}\n```'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], _Out)
    assert result.reply == "pong"


async def test_retries_once_then_succeeds() -> None:
    client = FakeLLMClient(["not json", '{"reply":"pong"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], _Out)
    assert result.reply == "pong"
    assert len(client.calls) == 2


async def test_raises_after_two_failures() -> None:
    client = FakeLLMClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        await complete_structured(client, "m", [{"role": "user", "content": "x"}], _Out)
