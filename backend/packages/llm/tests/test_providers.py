import pytest

from llm.providers import (
    PRESETS,
    OpenAICompatibleClient,
    ProviderPreset,
    attribution_headers,
    build_client,
    get_preset,
    resolve_base_url,
)


def test_presets_cover_expected_vendors() -> None:
    assert set(PRESETS) == {"openai", "openrouter", "ollama", "vllm"}
    assert isinstance(PRESETS["openrouter"], ProviderPreset)


def test_get_preset_known() -> None:
    assert get_preset("openrouter").base_url == "https://openrouter.ai/api/v1"


def test_get_preset_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_preset("nope")


def test_resolve_base_url_uses_preset_when_no_override() -> None:
    assert resolve_base_url("openai", "") == "https://api.openai.com/v1"


def test_resolve_base_url_override_wins() -> None:
    url = "http://host.docker.internal:11434/v1"
    assert resolve_base_url("ollama", url) == url


def test_attribution_headers_builds_pairs() -> None:
    assert attribution_headers("https://ei.tempo.co", "Editorial Intelligence") == (
        ("HTTP-Referer", "https://ei.tempo.co"),
        ("X-Title", "Editorial Intelligence"),
    )


def test_attribution_headers_empty() -> None:
    assert attribution_headers("", "") == ()



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
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs: object) -> _Completion:
        self.calls.append(kwargs)
        return _Completion("ok")


class _Chat:
    def __init__(self) -> None:
        self.completions = _Completions()


class _RawClient:
    def __init__(self) -> None:
        self.chat = _Chat()


async def test_complete_returns_content_and_sets_json_mode() -> None:
    raw = _RawClient()
    client = OpenAICompatibleClient(raw, supports_json_mode=True)
    out = await client.complete(model="m", messages=[{"role": "user", "content": "x"}])
    assert out == "ok"
    call = raw.chat.completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["temperature"] == 0


async def test_complete_omits_json_mode_when_unsupported() -> None:
    raw = _RawClient()
    client = OpenAICompatibleClient(raw, supports_json_mode=False)
    await client.complete(model="m", messages=[{"role": "user", "content": "x"}])
    assert "response_format" not in raw.chat.completions.calls[0]


def test_build_client_caches_identical_args() -> None:
    a = build_client("openai", "k", "", 60.0, ())
    b = build_client("openai", "k", "", 60.0, ())
    assert a is b
    assert isinstance(a, OpenAICompatibleClient)


def test_build_client_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        build_client("nope", "k", "", 60.0, ())
