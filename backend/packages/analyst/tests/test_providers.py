import pytest

from analyst.providers import (
    PRESETS,
    ProviderPreset,
    attribution_headers,
    get_preset,
    resolve_base_url,
)


def test_presets_cover_expected_vendors() -> None:
    assert set(PRESETS) == {"openai", "openrouter", "ollama", "vllm"}
    assert isinstance(PRESETS["openrouter"], ProviderPreset)


def test_get_preset_known() -> None:
    assert get_preset("openrouter").base_url == "https://openrouter.ai/api/v1"


def test_get_preset_unknown_raises() -> None:
    with pytest.raises(ValueError):
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
