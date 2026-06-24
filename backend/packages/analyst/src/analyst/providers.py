import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
