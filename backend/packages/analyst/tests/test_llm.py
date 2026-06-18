import pytest
from analyst.llm import complete_structured
from analyst.schemas import RecommendationInsight


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[dict] = []

    async def create(self, **kwargs: object) -> _Completion:
        self.calls.append(kwargs)
        return _Completion(self._contents[len(self.calls) - 1])


class _Chat:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _Completions(contents)


class FakeClient:
    def __init__(self, contents: list[str]) -> None:
        self.chat = _Chat(contents)


async def test_parses_valid_json() -> None:
    client = FakeClient(['{"title":"t","insight":"i","action":"a"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.title == "t"


async def test_strips_code_fences() -> None:
    client = FakeClient(['```json\n{"title":"t","insight":"i","action":"a"}\n```'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.action == "a"


async def test_retries_once_then_succeeds() -> None:
    client = FakeClient(["not json", '{"title":"t","insight":"i","action":"a"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.insight == "i"
    assert len(client.chat.completions.calls) == 2


async def test_raises_after_two_failures() -> None:
    client = FakeClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
