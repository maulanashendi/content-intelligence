from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI


@dataclass(frozen=True)
class ProviderPreset:
    base_url: str
    supports_json_mode: bool = True


PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset("https://api.openai.com/v1"),
    "openrouter": ProviderPreset("https://openrouter.ai/api/v1"),
    "ollama": ProviderPreset("http://localhost:11434/v1"),
    "vllm": ProviderPreset("http://localhost:8000/v1"),
}


def get_preset(provider: str) -> ProviderPreset:
    try:
        return PRESETS[provider]
    except KeyError:
        raise ValueError(
            f"Unknown analyst LLM provider: {provider!r}. Expected one of {sorted(PRESETS)}"
        ) from None


def resolve_base_url(provider: str, override: str) -> str:
    return override or get_preset(provider).base_url


def attribution_headers(referer: str, title: str) -> tuple[tuple[str, str], ...]:
    headers: list[tuple[str, str]] = []
    if referer:
        headers.append(("HTTP-Referer", referer))
    if title:
        headers.append(("X-Title", title))
    return tuple(headers)


class LLMClient(Protocol):
    async def complete(self, *, model: str, messages: list[dict[str, str]]) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, raw_client: AsyncOpenAI, supports_json_mode: bool) -> None:
        self._client = raw_client
        self._supports_json_mode = supports_json_mode

    async def complete(self, *, model: str, messages: list[dict[str, str]]) -> str:
        kwargs: dict = {"model": model, "messages": messages, "temperature": 0}
        if self._supports_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


@lru_cache(maxsize=8)
def build_client(
    provider: str,
    api_key: str,
    base_url_override: str,
    timeout: float,
    headers: tuple[tuple[str, str], ...],
) -> OpenAICompatibleClient:
    preset = get_preset(provider)
    base_url = resolve_base_url(provider, base_url_override)
    raw = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key or "not-needed",
        timeout=timeout,
        # openai SDK treats an empty dict the same as no headers; None is the correct sentinel
        default_headers=dict(headers) or None,
    )
    return OpenAICompatibleClient(raw, preset.supports_json_mode)
