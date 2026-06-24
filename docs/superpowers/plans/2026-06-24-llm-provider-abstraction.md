# LLM Provider Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isolate all hosted-LLM vendor coupling in the `analyst` package into one file (`analyst/providers.py`) behind an `LLMClient` protocol + preset table, so switching OpenAI-compatible vendors (OpenRouter/Ollama/vLLM) is a `.env` change and a future native-incompatible vendor touches one file.

**Architecture:** New `analyst/providers.py` owns the `openai` SDK import, a `PRESETS` table, the `LLMClient` protocol, and `OpenAICompatibleClient` + `build_client` factory. `analyst/config.py` gains a single `ANALYST_LLM_PROVIDER` switch and drops per-task base URLs. `analyst/llm.py` keeps only vendor-agnostic JSON-coaxing/retry and calls the provider through the protocol. Local models (embedding, labeling) are documented, not abstracted.

**Tech Stack:** Python 3.11+, `openai>=1.40` (already a dep), `pydantic-settings>=2`, pytest (async, `asyncio_mode=auto`).

**Reference spec:** `docs/superpowers/specs/2026-06-24-llm-provider-abstraction-design.md`

## Global Constraints

- Scope is the `analyst` package only; do NOT touch `embedding`/`labeling`/`clustering`/`scoring` code (they are documented, not abstracted).
- src layout per package; `analyst` code lives under `backend/packages/analyst/src/analyst/`.
- No new top-level dependencies (`openai` is already declared in `analyst/pyproject.toml`); if that changes, update `docs/tech-stack.md` in the same commit.
- No comments explaining WHAT; only non-obvious WHY.
- All logs are JSON via `core.logging`; no `print()`.
- `analyst` never imports ML modules (torch/transformers/etc.) — keep it `openai`-only.
- Run tests from `backend/` with `./.venv/bin/python -m pytest` (host unit tests are allowed; not `uv run`).
- Commit messages follow Conventional Commits and end with the trailer:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- No API endpoint changes; the `/api/v1/analyst/*` contract and its API-layer tests stay untouched (they mock `analyze.run_analysis` / `recommend.run_recommendation`).

---

### Task 1: Provider preset table + pure resolution layer

**Files:**
- Create: `backend/packages/analyst/src/analyst/providers.py`
- Test: `backend/packages/analyst/tests/test_providers.py`

**Interfaces:**
- Produces:
  - `ProviderPreset(base_url: str, supports_json_mode: bool = True)` — frozen dataclass
  - `PRESETS: dict[str, ProviderPreset]` — keys: `openai`, `openrouter`, `ollama`, `vllm`
  - `get_preset(provider: str) -> ProviderPreset` — raises `ValueError` on unknown
  - `resolve_base_url(provider: str, override: str) -> str` — `override or preset.base_url`
  - `attribution_headers(referer: str, title: str) -> tuple[tuple[str, str], ...]`

- [ ] **Step 1: Write the failing tests**

Create `backend/packages/analyst/tests/test_providers.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_providers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analyst.providers'`

- [ ] **Step 3: Create the providers module (pure layer only)**

Create `backend/packages/analyst/src/analyst/providers.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_providers.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/packages/analyst/src/analyst/providers.py backend/packages/analyst/tests/test_providers.py
git commit -m "feat(analyst): provider preset table + base-url/header resolution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: OpenAI-compatible client wrapper + cached factory

**Files:**
- Modify: `backend/packages/analyst/src/analyst/providers.py`
- Test: `backend/packages/analyst/tests/test_providers.py`

**Interfaces:**
- Consumes: `get_preset`, `ProviderPreset` (Task 1)
- Produces:
  - `class LLMClient(Protocol)` with `async def complete(self, *, model: str, messages: list[dict[str, str]]) -> str`
  - `class OpenAICompatibleClient` — `__init__(self, raw_client, supports_json_mode: bool)`, implements `complete`
  - `build_client(provider: str, api_key: str, base_url_override: str, timeout: float, headers: tuple[tuple[str, str], ...]) -> OpenAICompatibleClient` (lru_cached)

- [ ] **Step 1: Write the failing tests**

Append to `backend/packages/analyst/tests/test_providers.py`:

```python
from analyst.providers import OpenAICompatibleClient, build_client


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
    with pytest.raises(ValueError):
        build_client("nope", "k", "", 60.0, ())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_providers.py -v`
Expected: FAIL with `ImportError: cannot import name 'OpenAICompatibleClient'`

- [ ] **Step 3: Add the client wrapper + factory**

Edit `backend/packages/analyst/src/analyst/providers.py`. Change the imports at the top to:

```python
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI
```

Then append after `attribution_headers`:

```python
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
    base_url = base_url_override or preset.base_url
    raw = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key or "not-needed",
        timeout=timeout,
        default_headers=dict(headers) or None,
    )
    return OpenAICompatibleClient(raw, preset.supports_json_mode)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_providers.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/packages/analyst/src/analyst/providers.py backend/packages/analyst/tests/test_providers.py
git commit -m "feat(analyst): LLMClient protocol + OpenAI-compatible client factory

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Switch config + llm to the provider model (atomic refactor)

These two files change together: removing `base_url_for` from config breaks `llm.py`, so config and llm are refactored and committed as one unit. Tests are updated first (TDD), then both modules.

**Files:**
- Modify: `backend/packages/analyst/src/analyst/config.py`
- Modify: `backend/packages/analyst/src/analyst/llm.py`
- Test: `backend/packages/analyst/tests/test_config.py` (rewrite)
- Test: `backend/packages/analyst/tests/test_llm.py` (rewrite fake client)

**Interfaces:**
- Consumes: `providers.build_client`, `providers.attribution_headers`, `providers.LLMClient` (Tasks 1–2)
- Produces:
  - `AnalystSettings` fields: `analyst_llm_provider="openai"`, `analyst_llm_api_key=""`, `analyst_llm_base_url=""`, `analyst_request_timeout_seconds=60.0`, `analyst_attribution_referer=""`, `analyst_attribution_title=""`, `analyst_analyze_model="gpt-4o"`, `analyst_recommend_model="gpt-4o"`; method `model_for(task) -> str`
  - `llm.complete_structured(client: LLMClient, model: str, messages: list[dict[str, str]], schema: type[T]) -> T`
  - `llm.complete_for_task(task: str, messages: list[dict[str, str]], schema: type[T]) -> T`
  - Removed: `config.base_url_for`, `analyst_analyze_base_url`, `analyst_recommend_base_url`, `llm.get_async_client`

- [ ] **Step 1: Rewrite the config tests**

Replace the entire contents of `backend/packages/analyst/tests/test_config.py` with:

```python
import pytest

from analyst.config import AnalystSettings


def test_defaults() -> None:
    s = AnalystSettings(_env_file=None)
    assert s.analyst_llm_provider == "openai"
    assert s.analyst_llm_base_url == ""
    assert s.analyst_request_timeout_seconds == 60.0
    assert s.model_for("analyze") == "gpt-4o"
    assert s.model_for("recommend") == "gpt-4o"


def test_model_for_rejects_unknown_task() -> None:
    s = AnalystSettings(_env_file=None)
    with pytest.raises(ValueError):
        s.model_for("translate")


def test_per_task_base_url_is_gone() -> None:
    s = AnalystSettings(_env_file=None)
    assert not hasattr(s, "base_url_for")
    assert not hasattr(s, "analyst_analyze_base_url")
```

- [ ] **Step 2: Rewrite the llm test's fake client**

In `backend/packages/analyst/tests/test_llm.py`, replace the fake-client classes (lines 6–38, the `_Msg`/`_Choice`/`_Completion`/`_Completions`/`_Chat`/`FakeClient` block) with a single fake implementing the new `LLMClient.complete` interface:

```python
class FakeLLMClient:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[dict] = []

    async def complete(self, *, model: str, messages: list[dict]) -> str:
        self.calls.append({"model": model, "messages": messages})
        return self._contents[len(self.calls) - 1]
```

Then update the four test bodies to construct `FakeLLMClient(...)` instead of `FakeClient(...)`, and change the retry assertion from `len(client.chat.completions.calls) == 2` to `len(client.calls) == 2`. The full file becomes:

```python
import pytest

from analyst.llm import complete_structured
from analyst.schemas import RecommendationInsight


class FakeLLMClient:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[dict] = []

    async def complete(self, *, model: str, messages: list[dict]) -> str:
        self.calls.append({"model": model, "messages": messages})
        return self._contents[len(self.calls) - 1]


async def test_parses_valid_json() -> None:
    client = FakeLLMClient(['{"title":"t","insight":"i","action":"a"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.title == "t"


async def test_strips_code_fences() -> None:
    client = FakeLLMClient(['```json\n{"title":"t","insight":"i","action":"a"}\n```'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.action == "a"


async def test_retries_once_then_succeeds() -> None:
    client = FakeLLMClient(["not json", '{"title":"t","insight":"i","action":"a"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.insight == "i"
    assert len(client.calls) == 2


async def test_raises_after_two_failures() -> None:
    client = FakeLLMClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_config.py packages/analyst/tests/test_llm.py -v`
Expected: FAIL — `test_config` fails on missing `analyst_llm_provider`; `test_llm` fails because `complete_structured` still calls `client.chat.completions.create` (AttributeError on `FakeLLMClient`).

- [ ] **Step 4: Rewrite `config.py`**

Replace the entire contents of `backend/packages/analyst/src/analyst/config.py` with:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_TASKS = frozenset({"analyze", "recommend"})


class AnalystSettings(BaseSettings):
    """Config for the Editorial AI Analyst.

    Vendor switch: set analyst_llm_provider to a preset name
    (openai | openrouter | ollama | vllm). base_url + headers come from the
    preset table in analyst/providers.py; analyst_llm_base_url overrides the
    preset base_url only for self-hosted endpoints whose host:port can't live
    in a static preset.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    analyst_llm_provider: str = "openai"
    analyst_llm_api_key: str = ""
    analyst_llm_base_url: str = ""
    analyst_request_timeout_seconds: float = 60.0
    analyst_attribution_referer: str = ""
    analyst_attribution_title: str = ""

    analyst_analyze_model: str = "gpt-4o"
    analyst_recommend_model: str = "gpt-4o"

    def model_for(self, task: str) -> str:
        if task not in _VALID_TASKS:
            raise ValueError(f"Unknown analyst task: {task!r}. Expected one of {sorted(_VALID_TASKS)}")
        return getattr(self, f"analyst_{task}_model")


settings = AnalystSettings()
```

- [ ] **Step 5: Rewrite `llm.py`**

Replace the entire contents of `backend/packages/analyst/src/analyst/llm.py` with:

```python
import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from analyst import providers
from analyst.config import settings
from analyst.providers import LLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
    return text.strip()


def _augment(messages: list[dict[str, str]], schema: type[BaseModel]) -> list[dict[str, str]]:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    suffix = f"\n\nRespond ONLY with a single valid JSON object matching this schema:\n{schema_json}"
    out = [dict(m) for m in messages]
    for m in out:
        if m["role"] == "system":
            m["content"] = m["content"] + suffix
            return out
    out.insert(0, {"role": "system", "content": suffix.strip()})
    return out


async def complete_structured(
    client: LLMClient,
    model: str,
    messages: list[dict[str, str]],
    schema: type[T],
) -> T:
    augmented = _augment(messages, schema)
    last_exc: Exception | None = None
    for attempt in (1, 2):
        raw = await client.complete(model=model, messages=augmented)
        try:
            return schema.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning(
                "analyst llm returned invalid structured output",
                extra={"attempt": attempt, "schema": schema.__name__},
            )
    raise ValueError(f"LLM returned invalid output for {schema.__name__}: {last_exc}")


async def complete_for_task(
    task: str, messages: list[dict[str, str]], schema: type[T]
) -> T:
    client = providers.build_client(
        settings.analyst_llm_provider,
        settings.analyst_llm_api_key,
        settings.analyst_llm_base_url,
        settings.analyst_request_timeout_seconds,
        providers.attribution_headers(
            settings.analyst_attribution_referer,
            settings.analyst_attribution_title,
        ),
    )
    return await complete_structured(client, settings.model_for(task), messages, schema)
```

- [ ] **Step 6: Run the full analyst suite to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/ -v`
Expected: PASS (all analyst tests, including providers/config/llm/analyze/recommend/category/schemas)

- [ ] **Step 7: Run the API analyst suite to confirm no contract regression**

Run: `cd backend && ./.venv/bin/python -m pytest packages/api/tests/analyst/ -v`
Expected: PASS (these mock `run_analysis`/`run_recommendation`; unaffected by the refactor)

- [ ] **Step 8: Commit**

```bash
git add backend/packages/analyst/src/analyst/config.py backend/packages/analyst/src/analyst/llm.py backend/packages/analyst/tests/test_config.py backend/packages/analyst/tests/test_llm.py
git commit -m "refactor(analyst): single provider switch; llm calls vendor via LLMClient

Drop per-task base URLs and the direct openai import in llm.py. config now
exposes ANALYST_LLM_PROVIDER (+ attribution + optional base_url override);
llm.py builds the client through providers.build_client.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Env example + model documentation

No automated test cycle (docs + env). The deliverable is verified by reading the rendered files and confirming the OpenRouter switch is a pure `.env` change.

**Files:**
- Modify: `backend/.env.example`
- Create: `docs/llm-models.md`
- Modify: `docs/tech-stack.md` (the `openai` row)
- Modify: `CLAUDE.md` (the `analyst` module row)
- Modify: `docs/README.md` (routing table — add one row)

- [ ] **Step 1: Update `.env.example`**

In `backend/.env.example`, replace the Editorial AI Analyst block (the lines currently setting `ANALYST_LLM_BASE_URL` / `ANALYST_LLM_API_KEY` / `ANALYST_ANALYZE_MODEL` / `ANALYST_RECOMMEND_MODEL`, around lines 57–63) with:

```bash
# --- Editorial AI Analyst (D37) ---
# Switch vendor by name; base_url + headers come from the preset table in
# analyst/providers.py. Presets: openai | openrouter | ollama | vllm
ANALYST_LLM_PROVIDER=openai
ANALYST_LLM_API_KEY=
# Optional: override the preset base_url (required for self-hosted ollama/vllm host:port).
ANALYST_LLM_BASE_URL=
# Model ids are vendor-specific. OpenRouter uses "vendor/model", e.g. openai/gpt-4o.
ANALYST_ANALYZE_MODEL=gpt-4o
ANALYST_RECOMMEND_MODEL=gpt-4o
# Optional OpenRouter attribution headers:
ANALYST_ATTRIBUTION_REFERER=
ANALYST_ATTRIBUTION_TITLE=
#
# OpenRouter example:
#   ANALYST_LLM_PROVIDER=openrouter
#   ANALYST_LLM_API_KEY=sk-or-...
#   ANALYST_ANALYZE_MODEL=openai/gpt-4o
#   ANALYST_RECOMMEND_MODEL=openai/gpt-4o
```

- [ ] **Step 2: Create `docs/llm-models.md`**

Create `docs/llm-models.md`:

```markdown
# LLM & Model Inventory

Which models this project runs, for what, and whether they are hosted **API**
calls or **local** on-box weights. Vendor switching for the API LLM is covered
in §"Switching the API vendor".

## API models — `analyst` package (hosted LLM)

The Editorial AI Analyst is the only code that calls a hosted LLM over HTTP.

| Task | Purpose | Default model | Env var |
| --- | --- | --- | --- |
| `analyze` | Extract article attributes + editorial feedback | `gpt-4o` | `ANALYST_ANALYZE_MODEL` |
| `recommend` | Extract data filters, then generate insights (two LLM calls) | `gpt-4o` | `ANALYST_RECOMMEND_MODEL` |

- Client: `openai` SDK, behind the vendor boundary in `analyst/providers.py`.
- Structured output: the schema is injected into the prompt and, when the
  provider supports it, `response_format={"type":"json_object"}` is set; output
  is validated against a Pydantic schema with one retry.

### Switching the API vendor

Switching among OpenAI-compatible vendors is a `.env` change only:

1. Set `ANALYST_LLM_PROVIDER` to a preset name.
2. Set `ANALYST_LLM_API_KEY`.
3. Set the model ids to the vendor's format (OpenRouter uses `vendor/model`).
4. For self-hosted endpoints, set `ANALYST_LLM_BASE_URL` to override the host:port.

Preset table (`analyst/providers.py`):

| Provider | Base URL | Notes |
| --- | --- | --- |
| `openai` | `https://api.openai.com/v1` | Default |
| `openrouter` | `https://openrouter.ai/api/v1` | Optional `HTTP-Referer`/`X-Title` via `ANALYST_ATTRIBUTION_*` |
| `ollama` | `http://localhost:11434/v1` | Self-hosted; override base URL for non-local host |
| `vllm` | `http://localhost:8000/v1` | Self-hosted; override base URL for non-local host |

A future native-incompatible vendor (e.g. Anthropic Messages API) is added by
implementing a new `LLMClient` in `analyst/providers.py` plus a preset entry —
no change to `llm.py` or the callers.

## Local models — on-box weights (not vendor-swappable)

| Purpose | Model | Format | Library | Device | Driven by |
| --- | --- | --- | --- | --- | --- |
| Article embedding (768d) | `google/embeddinggemma-300m` | HuggingFace | `sentence-transformers` + `torch` (CPU) | CPU | `EMBEDDING_MODEL_NAME` |
| Cluster labeling | `bartowski/gemma-2-2b-it-GGUF` (`Q4_K_M`) | GGUF 4-bit | `llama-cpp-python` | CPU (`n_gpu_layers=0`) | hardcoded in `labeling/llm.py` |

- The embedding dimension is fixed at `vector(768)`; swapping the embedding
  model requires a DB migration plus a full re-embed (see `decisions.md` D4).
- ⚠️ The labeling model id is hardcoded in `backend/packages/labeling/src/labeling/llm.py`;
  the `LLM_MODEL_NAME` env var is documented but not read. Tracked as a known
  inconsistency, out of scope for the provider abstraction.

## ML (non-LLM)

| Purpose | Package | Libraries |
| --- | --- | --- |
| Dimensionality reduction → clustering | `clustering` | `umap-learn` → `hdbscan` |
| Scoring (velocity, novelty, coverage) | `scoring` | `scikit-learn`, `numpy` |

## Env var reference

**API (analyst):** `ANALYST_LLM_PROVIDER`, `ANALYST_LLM_API_KEY`,
`ANALYST_LLM_BASE_URL` (optional override), `ANALYST_ANALYZE_MODEL`,
`ANALYST_RECOMMEND_MODEL`, `ANALYST_ATTRIBUTION_REFERER`,
`ANALYST_ATTRIBUTION_TITLE`, `ANALYST_REQUEST_TIMEOUT_SECONDS`.

**Local models:** `EMBEDDING_MODEL_NAME`, `EMBEDDING_MODEL_VERSION`,
`LLM_MODEL_NAME` (documented; see warning above), `LLM_MODEL_VERSION`,
`HF_HOME`, `HF_TOKEN`.
```

- [ ] **Step 3: Update `docs/tech-stack.md`**

Find the `openai` row (the line beginning `` | `openai` >=1.40 ``) and replace its rightmost cell so the row reads:

```markdown
| `openai` >=1.40 (currently 2.43.x) | OpenAI-compatible HTTP client for the `analyst` package | Vendor coupling isolated in `analyst/providers.py`; switch vendor via `ANALYST_LLM_PROVIDER` (see `docs/llm-models.md`). Local vs API = base-URL swap, no torch. |
```

- [ ] **Step 4: Update `CLAUDE.md`**

In the Modules table, replace the `analyst` row's Notes cell so the row reads:

```markdown
| `analyst`    | Editorial AI Analyst: article scoring + recommendation | openai SDK behind `providers.py` vendor boundary; switch vendor via `ANALYST_LLM_PROVIDER`; no ML import |
```

- [ ] **Step 5: Update `docs/README.md` routing table**

Add one row to the doc routing table pointing readers to the new inventory:

```markdown
| Which models we run, local vs API, and how to switch the LLM vendor | `docs/llm-models.md` |
```

- [ ] **Step 6: Verify the docs render and links resolve**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/ -q`
Expected: PASS (sanity re-run; docs changes don't affect code).
Then manually confirm `docs/llm-models.md` exists and the OpenRouter example in `.env.example` matches the preset names in `analyst/providers.py`.

- [ ] **Step 7: Commit**

```bash
git add backend/.env.example docs/llm-models.md docs/tech-stack.md CLAUDE.md docs/README.md
git commit -m "docs(analyst): model inventory + vendor-switch guide; OpenRouter env example

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §4.1 providers.py (presets, protocol, client, factory, attribution) → Tasks 1–2 ✓
- §4.2 config changes (provider switch, attribution, optional base_url, remove per-task) → Task 3 ✓
- §4.3 llm.py slimming (drop openai import/get_async_client, use providers, LLMClient) → Task 3 ✓
- §4.5 upgrade path → documented in Task 4 (`docs/llm-models.md`) ✓
- §5 `.env.example` → Task 4 Step 1 ✓
- §6 `docs/llm-models.md` + tech-stack/CLAUDE.md/README → Task 4 ✓
- §7 breaking change (removed per-task base URLs) → Task 3 (config rewrite) + asserted in `test_per_task_base_url_is_gone` ✓
- §8 testing (test_providers new; test_config/test_llm updates; api analyst suite green) → Tasks 1–3 ✓

**Placeholder scan:** No TBD/TODO; every code/doc step contains full content.

**Type consistency:** `LLMClient.complete(*, model, messages) -> str` is defined in Task 2 and consumed identically by `complete_structured` (Task 3) and the `FakeLLMClient` test (Task 3). `build_client(provider, api_key, base_url_override, timeout, headers)` signature matches its call site in `complete_for_task` (Task 3). `attribution_headers` returns a `tuple[tuple[str,str], ...]`, matching the hashable `headers` param of `build_client`.
```
