# LLM Provider Abstraction — Design

- **Date:** 2026-06-24
- **Status:** Approved (brainstorming) → pending implementation plan
- **Scope owner:** `backend/packages/analyst`
- **Related:** D37 (Editorial AI Analyst), `docs/tech-stack.md`, `docs/constraints.md`

## 1. Context & goal

The `analyst` package is the only code that calls a hosted LLM **API**. Today the vendor coupling is spread across `analyst/llm.py` (the `openai` SDK import, client construction, call shape, response parsing) and `analyst/config.py` (base URL / model / key).

We are migrating to **OpenRouter** now and may switch vendors again later. The goal: switching among OpenAI-compatible vendors must be a `.env` change only, and adding a future **native-incompatible** vendor (e.g. Anthropic Messages API, Gemini native) must touch **one file**, leaving `llm.py` and all callers untouched.

Key fact that shapes the design: **OpenRouter is OpenAI-SDK-compatible** (same `openai` client, base URL `https://openrouter.ai/api/v1`). So the OpenRouter migration itself needs zero new client code — only configuration. The abstraction exists to (a) make that config a clean single switch and (b) create the seam for a non-compatible vendor later.

## 2. Scope

**In scope (code changes):** `analyst` package only — `config.py`, `llm.py`, new `providers.py`, tests, `.env.example`.

**In scope (docs):** new `docs/llm-models.md` reference; minor updates to `docs/tech-stack.md` and the `analyst` line in `CLAUDE.md`.

**Out of scope:** the local models (`embedding` = `embeddinggemma-300m`, `labeling` = Gemma 2B GGUF). These are HuggingFace weights run on-box, not vendor-swappable via API. They are *documented* in `docs/llm-models.md` but not placed behind this abstraction. Clustering (UMAP/HDBSCAN) and scoring (sklearn/numpy) are not LLMs and are only named in the doc.

**Approach chosen:** Provider boundary module (rejected: config-only — leaves SDK in `llm.py`; rejected: full registry/strategy — speculative, YAGNI).

## 3. Model inventory (current state)

The full version lives in the `docs/llm-models.md` deliverable (§6). Condensed:

| Layer | Where | Model (default) | Driven by | Library |
|---|---|---|---|---|
| API LLM — `analyze` | `analyst` | `gpt-4o` | `ANALYST_ANALYZE_MODEL` | `openai` SDK |
| API LLM — `recommend` (2 calls) | `analyst` | `gpt-4o` | `ANALYST_RECOMMEND_MODEL` | `openai` SDK |
| Local embedding (768d) | `embedding` | `google/embeddinggemma-300m` | `EMBEDDING_MODEL_NAME` ✅ | `sentence-transformers` + `torch` CPU |
| Local labeling | `labeling` | `bartowski/gemma-2-2b-it-GGUF` (Q4_K_M) | hardcoded `labeling/llm.py:22-23` ⚠️ | `llama-cpp-python` CPU |
| ML clustering | `clustering` | — | — | `umap-learn` → `hdbscan` |
| ML scoring | `scoring` | — | — | `scikit-learn`, `numpy` |

> Noted-but-out-of-scope inconsistency: `labeling` hardcodes its model id; `LLM_MODEL_NAME` env exists but is never read. Documented in `docs/llm-models.md`; not fixed by this work.

## 4. Design

### 4.1 New file `analyst/providers.py` — the vendor boundary

This is the only file that imports the vendor SDK and knows the call/response shape.

- **Preset table** `PRESETS: dict[str, ProviderPreset]`. A `ProviderPreset` is a frozen dataclass: `base_url: str`, `supports_json_mode: bool = True`. Initial entries:
  - `openai` → `https://api.openai.com/v1`
  - `openrouter` → `https://openrouter.ai/api/v1`
  - `ollama` → `http://localhost:11434/v1`
  - `vllm` → `http://localhost:8000/v1`
- **Protocol** `LLMClient`: `async def complete(self, *, model: str, messages: list[dict[str, str]]) -> str` returning the raw assistant text. `response_format` is a vendor detail and does **not** appear in this interface.
- **Implementation** `OpenAICompatibleClient(LLMClient)`: owns `from openai import AsyncOpenAI`, constructs the client with `base_url`, `api_key or "not-needed"`, `timeout`, and `default_headers`. In `complete()` it passes `temperature=0` and adds `response_format={"type": "json_object"}` only when its preset's `supports_json_mode` is true; returns `response.choices[0].message.content or ""`.
- **Factory** `build_client(provider, api_key, base_url_override, timeout, headers) -> LLMClient`, `@lru_cache`d. Resolves preset (raises `ValueError` on unknown provider), applies `base_url_override or preset.base_url`, builds the client. `headers` is passed as a hashable tuple of pairs so the call stays cacheable.
- **Helper** `attribution_headers(referer, title) -> tuple[tuple[str, str], ...]`: builds `HTTP-Referer` / `X-Title` pairs (OpenRouter attribution) when set; empty otherwise. Harmless for other vendors.

### 4.2 `analyst/config.py` — changes

```
+ analyst_llm_provider: str = "openai"          # selects a PRESETS entry
+ analyst_attribution_referer: str = ""         # OpenRouter HTTP-Referer
+ analyst_attribution_title: str = ""           # OpenRouter X-Title
~ analyst_llm_base_url: str = ""                # now OPTIONAL override; "" → preset base_url
  analyst_llm_api_key: str = ""                 # unchanged
  analyst_request_timeout_seconds: float = 60.0 # unchanged
  analyst_analyze_model: str = "gpt-4o"         # unchanged
  analyst_recommend_model: str = "gpt-4o"       # unchanged
- analyst_analyze_base_url / analyst_recommend_base_url   # removed
- base_url_for(task)                            # removed
  model_for(task)                               # unchanged (still validates _VALID_TASKS)
```

Preset resolution lives in `providers.py`, not `config.py`. Config holds only raw values.

### 4.3 `analyst/llm.py` — slimmed to vendor-agnostic orchestration

- **Removed:** `from openai import AsyncOpenAI`, `get_async_client`.
- **Kept (generic):** `_augment` (injects the JSON schema into the system prompt), `_extract_json` (strips markdown fences), the two-attempt retry loop.
- `complete_structured(client: LLMClient, model, messages, schema)` calls `client.complete(model=..., messages=...)` instead of `client.chat.completions.create(...)`, then validates against the Pydantic schema with retry.
- `complete_for_task(task, messages, schema)` builds the client via `providers.build_client(...)` from the config values + `providers.attribution_headers(...)`, then calls `complete_structured` with `settings.model_for(task)`.

### 4.4 Data flow

```
route → analyze/recommend → llm.complete_for_task(task, messages, schema)
        → providers.build_client(provider, key, base_url_override, timeout, headers)  [cached]
        → llm.complete_structured(client, model, messages, schema)   # augment + retry + validate
        → client.complete(model, messages)                            # vendor call lives here
```

### 4.5 Upgrade path (future native-incompatible vendor)

Add a new `class AnthropicClient(LLMClient)` (owns `anthropic` SDK, maps messages, returns raw text) and a `PRESETS` entry in `providers.py`; extend `build_client` to pick the implementation by provider. `llm.py`, the callers, and the routes do not change. This is the payoff of the boundary.

## 5. `.env.example` changes

```
# --- Editorial AI Analyst (D37) ---
# Switch vendor by name; base_url + headers come from the preset table in analyst/providers.py.
# Presets: openai | openrouter | ollama | vllm
ANALYST_LLM_PROVIDER=openai
ANALYST_LLM_API_KEY=
# Optional: override the preset base_url (required for self-hosted ollama/vllm host:port).
ANALYST_LLM_BASE_URL=
ANALYST_ANALYZE_MODEL=gpt-4o
ANALYST_RECOMMEND_MODEL=gpt-4o
# Optional OpenRouter attribution headers:
ANALYST_ATTRIBUTION_REFERER=
ANALYST_ATTRIBUTION_TITLE=
```

OpenRouter example (comment in the file): `ANALYST_LLM_PROVIDER=openrouter`, `ANALYST_LLM_API_KEY=sk-or-...`, `ANALYST_ANALYZE_MODEL=openai/gpt-4o`.

## 6. Documentation deliverable — `docs/llm-models.md`

New reference doc answering "which models, for what, local vs API". Structure:

1. **API models** — the `analyst` table (task → model → env), the two-call recommend flow, how to switch vendor (set `ANALYST_LLM_PROVIDER` + key + provider-style model id), the preset table, `supports_json_mode` note.
2. **Local models** — `embedding` (`embeddinggemma-300m`, 768d, `vector(768)` fixed, swap = migration + re-embed) and `labeling` (Gemma 2B GGUF, CPU, hardcoded id ⚠️).
3. **ML (non-LLM)** — clustering (UMAP→HDBSCAN), scoring (sklearn/numpy).
4. **Env var reference** — every model/LLM var grouped as local vs API.

Cross-link from `docs/README.md`'s routing table. Update `docs/tech-stack.md` `openai` row to mention the provider switch. Update the `analyst` line in `CLAUDE.md` to note the provider abstraction.

## 7. Migration & breaking changes

- **Breaking:** `ANALYST_ANALYZE_BASE_URL` / `ANALYST_RECOMMEND_BASE_URL` are removed. Any deployment relying on per-task endpoint split must move to a single `ANALYST_LLM_PROVIDER` (+ `ANALYST_LLM_BASE_URL` override). No current deployment is known to use the split.
- **Non-breaking:** existing `ANALYST_LLM_API_KEY`, `ANALYST_*_MODEL` keep working. Default provider `openai` reproduces today's behavior (`ANALYST_LLM_BASE_URL` empty → preset `https://api.openai.com/v1`).
- **Deferred upgrade hook:** per-task provider (`ANALYST_<task>_PROVIDER`) is not built now; documented as the way to restore split endpoints if ever needed.

## 8. Testing

- `test_providers.py` (new): unknown provider raises; `base_url_override` wins over preset; empty override falls back to preset; `attribution_headers` builds/omits correctly; `build_client` cache returns the same instance for identical args; `supports_json_mode=False` path omits `response_format`.
- `test_config.py` (update): new fields default correctly; removed fields/`base_url_for` gone; `model_for` still validates tasks.
- `test_llm.py` (update): `complete_structured` drives an injected fake `LLMClient` (no real SDK); retry-on-invalid-JSON and markdown-fence extraction still pass; `complete_for_task` wires config → client.
- Existing `analyst` and `api/tests/analyst` suites stay green (mock at the `LLMClient.complete` seam).

## 9. Out of scope / deferred

- Local model abstraction or env-driving the labeling model id.
- Per-task provider selection.
- Streaming, tool-calling, multi-turn — analyst is single-shot structured output.
- Provider registry/strategy framework (Approach 3).
