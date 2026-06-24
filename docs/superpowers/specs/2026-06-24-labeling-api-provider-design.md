# Labeling → API provider (SP2) — Design

- **Date:** 2026-06-24
- **Status:** Approved-pending-spec-review → implementation plan
- **Scope owner:** `backend/packages/labeling` (+ `core/config.py`, Dockerfile, `llm` pkg touch-up)
- **Parent effort:** Full-API / 2 GB VPS migration — **SP2 of 4**. SP1 (shared `llm` package) is merged.

## 1. Context & goal

The local Gemma 2B LLM (`labeling`, via `llama-cpp-python`) holds ~2–2.5 GB resident in the long-running pipeline daemon. Moving cluster labeling to an API frees that RAM (the largest single lever toward a 2 GB VPS). SP2 makes labeling backend-switchable (`local` Gemma | API via the shared `llm` package), defaulting to `local` so nothing changes until the operator flips the switch.

### Scope reality (verified against code — corrects the roadmap one-liner)
- Gemma has exactly **two production call sites, both per-cluster**, in `labeling/pipeline.py`: `generate_cluster_insight(reps)` (line 244, primary) and `generate_label(articles)` (line 265, fallback when insight yields no label).
- `labeling/analysis.py` is a **no-op stub** ("analysis folded into labeling pipeline"); `extract_article_claims` / `deduplicate_claims` have **no production caller**. → out of scope (no live Gemma use).
- `generate_label_and_insight` is **dead code** (tests only). → not ported.
- A **top-N cap already exists**: `_select_cluster_ids_for_labeling` slices to `settings.labeling_max_clusters` (default 100), ordered by `trend_match_count DESC, member_count DESC`. → "top-N" is already satisfied; SP2 keeps it.
- Cost at 100 clusters/run, ~1 call each (~2–4k input tokens), daily: with a cheap model (`openai/gpt-4o-mini` via OpenRouter) ≈ **$1–3/month**.

## 2. Decisions & assumptions (documented; veto at spec review)

1. **Single provider knob, unified with SP3.** `LABELING_PROVIDER` takes `local` (Gemma) **or** an `llm` preset name (`openai`/`openrouter`/`ollama`/`vllm`). `local` is the default (backward-compatible). Non-`local` → API path via the `llm` package using that preset. (Same shape SP3 will use for `EMBEDDING_PROVIDER`.)
2. **Config lives in `core/config.py`** (where `labeling_max_clusters` and other labeling knobs already live). No new settings module — follows the existing labeling pattern. (Analyst keeps its own `AnalystSettings`; not unified here — YAGNI.)
3. **Keep the existing cluster selection** (`trend_match_count` ordering, cap 100). SP2 is a backend swap, not a re-ranking. The pre-existing mismatch between labeling selection (trend) and API serving rank (`demand_score`) is left as-is; aligning them is a deferred, separate improvement.
4. **Structured JSON on the API path; regex stays on local.** The API path uses `llm.structured.complete_structured` with a Pydantic schema — no fragile prefix parsing. The Gemma local path keeps its existing `_parse_cluster_insight` regex (Gemma can't be trusted to emit clean JSON).
5. **Lazy import preserved.** `llama-cpp-python` is imported only on the `local` path (already the case in `get_llm`). When `LABELING_PROVIDER != local`, Gemma/llama-cpp is never imported or loaded → the RAM is freed at runtime. The package keeps `llama-cpp-python` as a dependency (one image; image size is acceptable per the operator).
6. **`llm.providers.get_preset` error string** is de-"analyst"-ified here (the SP1 backlog item) — labeling is the package's second consumer.

## 3. Architecture

```
labeling/pipeline.py  (unchanged orchestration; still calls generate_cluster_insight / generate_label)
        │
labeling/llm.py        dispatcher: local → Gemma (existing) | api → llm package
        ├── local path: get_llm() + _parse_cluster_insight   (llama-cpp; lazy)
        └── api   path: llm.providers.build_client + llm.structured.complete_structured(schema)
labeling/schemas.py    NEW — ClusterInsightLLM, ClusterLabelLLM (Pydantic)
labeling/prompts.py    + API-mode message builders (ask for the fields; JSON schema added by _augment)
core/config.py         + LABELING_PROVIDER / LABELING_MODEL / LABELING_LLM_* knobs
```

Downstream (`pipeline.py` persistence to `article_cluster.label` + `cluster_insight.*`) is unchanged: both paths return the same dict shape `{label, what_happened, parties_involved, editorial_angle, summary}`.

## 4. Components

### 4.1 `labeling/schemas.py` (new)
```python
from pydantic import BaseModel

class ClusterInsightLLM(BaseModel):
    label: str
    what_happened: str | None = None
    parties_involved: list[str] | None = None
    editorial_angle: str | None = None
    summary: list[str] | None = None

class ClusterLabelLLM(BaseModel):
    label: str
```

### 4.2 `core/config.py` (additions)
```
labeling_provider: str = "local"                  # local | openai | openrouter | ollama | vllm
labeling_model: str = "openai/gpt-4o-mini"
labeling_llm_api_key: str = ""
labeling_llm_base_url: str = ""                    # optional preset override
labeling_request_timeout_seconds: float = 60.0
labeling_attribution_referer: str = ""
labeling_attribution_title: str = ""
```
(`labeling_max_clusters`, `hf_home`, `hf_token` stay.)

### 4.3 `labeling/llm.py` (dispatcher)
- `generate_cluster_insight(reps)` → if `settings.labeling_provider == "local"`: existing Gemma body (renamed `_cluster_insight_local`); else `_cluster_insight_api(reps)`.
- `generate_label(articles)` → same local/api split (api returns `ClusterLabelLLM.label`).
- `_build_labeling_client()` → `llm.providers.build_client(settings.labeling_provider, settings.labeling_llm_api_key, settings.labeling_llm_base_url, settings.labeling_request_timeout_seconds, attribution_headers(...))`.
- `_cluster_insight_api(reps)` → trims reps to a token budget (reuse a char-based heuristic; no Gemma tokenizer on the API path), calls `complete_structured(client, settings.labeling_model, prompts.format_cluster_insight_messages_api(reps), ClusterInsightLLM)`, returns `result.model_dump()`.
- Gemma identity stays hardcoded (out of scope; the `local` path is unchanged).

### 4.4 `labeling/prompts.py` (additions)
- `format_cluster_insight_messages_api(reps)` and `format_label_messages_api(articles)`: same article context as the Gemma builders, but the instruction asks for the fields conceptually (label, what happened, parties, editorial angle, key claims) WITHOUT the `LABEL:`/`APA_TERJADI:` line-format directive — `complete_structured._augment` appends the JSON-schema instruction. Indonesian, consistent with existing prompts.

### 4.5 `llm/providers.py` touch-up
- `get_preset` error message: `"Unknown analyst LLM provider"` → `"Unknown LLM provider"`.

### 4.6 Dependencies & Docker
- `labeling/pyproject.toml`: add `"llm"` to deps + `llm = { workspace = true }`; keep `llama-cpp-python` (local path).
- `Dockerfile` `pipeline-build`: add `COPY packages/llm/src packages/llm/src` (pipeline now resolves `labeling → llm`). The `deps` stage already copies every `packages/*/pyproject.toml` after SP1.

## 5. Data flow (API mode)

```
cluster_label_score (daily) → scoring (SQL) → labeling.pipeline.run()
  → per top-N cluster: generate_cluster_insight(reps)
       → _cluster_insight_api → build_client(preset) → complete_structured(ClusterInsightLLM)
       → {label, what_happened, parties_involved, editorial_angle, summary}
  → persist article_cluster.label + cluster_insight.* (unchanged)
```

## 6. Error handling
- API path: `complete_structured` already retries once then raises `ValueError`. `pipeline.py`'s existing per-cluster try/except (it already logs and falls back / skips a cluster) covers API failures the same way it covers Gemma failures — confirm the existing except clause catches `ValueError`/`Exception` and skips, so one bad cluster never aborts the run.
- A cluster whose API call fails after retry is skipped (logged), same as today's Gemma failure behavior.

## 7. Testing
- `labeling/tests/test_llm.py`: add tests for the dispatcher — `labeling_provider="local"` routes to the Gemma path (mock `get_llm`), a preset value routes to `_cluster_insight_api` (mock `build_client`/`complete_structured`, assert the schema + model are passed and the returned dict shape matches the local parser's keys). Keep existing local-path parser tests.
- `core/tests` (or labeling): assert new config defaults (`labeling_provider == "local"`, etc.).
- A schema test: `ClusterInsightLLM` parses a representative JSON payload into the expected dict via `model_dump()`.
- No live API calls in tests (mock at `complete_structured`).
- Regression: existing labeling tests stay green; `local` default means the pipeline behaves identically without config.

## 8. Verification (manual, post-merge)
- With `LABELING_PROVIDER=openrouter` + `LABELING_MODEL=openai/gpt-4o-mini` + key set, run `python -m pipeline.cli label` (manual step) on a small run and confirm labels/insights populate `cluster_insight` and `llama-cpp`/Gemma never loads (RAM stays low; no "loading labeling llm" log).

## 9. Out of scope / deferred
- `analysis.py` / per-article claims (dead code; no Gemma).
- Embedding / `torch` removal (SP3).
- Docker 2 GB compose profile + postgres topology (SP4).
- Making the Gemma model id env-configurable, and aligning labeling selection to `demand_score` — separate improvements.
- Dropping `llama-cpp-python` from the image entirely (would need a separate API-only image; operator accepts one image).
