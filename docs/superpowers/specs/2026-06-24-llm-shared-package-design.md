# Shared `llm` Package (SP1) — Design

- **Date:** 2026-06-24
- **Status:** Approved (brainstorming) → pending implementation plan
- **Scope owner:** new `backend/packages/llm` + `backend/packages/analyst`
- **Parent effort:** "Full-API / 2 GB VPS" migration. This is **SP1 of 4**:
  - **SP1 (this doc):** extract the chat LLM provider abstraction into a shared `llm` package — enabler.
  - SP2: labeling → API (chat, top-N clusters, `LABELING_PROVIDER` switch, lazy-import `llama-cpp`).
  - SP3: embedding → API (new embedding capability in the `llm` package, `EMBEDDING_PROVIDER` switch, lazy-import `torch`, re-embed migration + cluster-quality validation).
  - SP4: Docker/compose 2 GB profile + deployment topology (postgres off-box).
- **Builds on:** `docs/superpowers/specs/2026-06-24-llm-provider-abstraction-design.md` (the analyst provider abstraction this extracts).

## 1. Context & goal

The chat-completion vendor abstraction built for `analyst` (`analyst/providers.py` + the structured-output orchestration in `analyst/llm.py`) must be reused by `labeling` (SP2). The project rule forbids batch modules importing each other ("share via core"). Rather than overload `core` (a DB kernel with no `openai` dependency), promote the LLM abstraction into a **new shared workspace package `llm`**. `core` stays DB-only; `llm` becomes a second shared kernel for LLM concerns.

SP1 is a **pure refactor**: move code, change no behavior. `analyst` produces byte-identical results; all existing tests stay green.

## 2. Scope

**In scope:**
- New package `backend/packages/llm` holding the chat provider abstraction + generic structured-output orchestration.
- Rewire `analyst` to depend on `llm`; delete the moved code from `analyst`.
- Workspace registration (`pyproject.toml`, `uv.lock`), Dockerfile copy steps for the new package.
- Docs: `CLAUDE.md` modules table + the "share via core" rule note; `tech-stack.md`.

**Out of scope (later SPs):**
- Any labeling/embedding change (SP2/SP3).
- Adding embedding capability to the `llm` package (SP3 — the package is designed to grow into it, but SP1 ships chat only).
- Any behavior, prompt, model, or config change.

**Decisions locked in brainstorming:**
- Placement: **new `llm` package** (not `core.llm`).
- `llm` is **config-agnostic** — it takes explicit params; app config (`AnalystSettings`, future `LabelingSettings`) stays in each consumer.
- SP1 ships **chat only**; embedding joins the same package in SP3.

## 3. Architecture

```
packages/
  core/      DB models, session, settings, logging      (no openai)
  llm/       NEW — shared LLM client kernel              (openai, pydantic; no core dep)
    src/llm/providers.py    presets + client + factory
    src/llm/structured.py   complete_structured + JSON coaxing + retry
  analyst/   depends on core + llm; keeps AnalystSettings + complete_for_task glue
```

Dependency direction: `analyst → llm`. `llm` depends on nothing internal (no `core`) — it is a leaf shared library, which keeps it trivially reusable by `labeling` (a batch module) without creating batch-to-batch coupling.

## 4. The `llm` package

### 4.1 `pyproject.toml`
```toml
[project]
name = "llm"
version = "0.1.0"
description = "Shared LLM client kernel: OpenAI-compatible provider presets + structured output"
requires-python = ">=3.11"
dependencies = ["openai>=1.40", "pydantic>=2"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/llm"]
```
No `[tool.uv.sources]` block (no workspace deps).

### 4.2 `src/llm/providers.py`
Moved verbatim from `analyst/providers.py` (no logic change): `ProviderPreset`, `PRESETS` (openai/openrouter/ollama/vllm), `get_preset`, `resolve_base_url`, `attribution_headers`, `LLMClient` (Protocol), `OpenAICompatibleClient`, `build_client` (lru_cached, reuses `resolve_base_url`).

### 4.3 `src/llm/structured.py`
Moved from `analyst/llm.py` (no logic change): `complete_structured(client: LLMClient, model, messages, schema) -> T`, plus the private `_augment` and `_extract_json`. Imports `LLMClient` from `llm.providers`. Uses stdlib `logging.getLogger(__name__)` (no `core` dependency; the entry-point's `configure_logging()` still formats it).

### 4.4 `tests/`
- `tests/test_providers.py` — moved from `analyst/tests/test_providers.py` (imports rebased to `llm.providers`).
- `tests/test_structured.py` — the generic `complete_structured` tests moved from `analyst/tests/test_llm.py` (FakeLLMClient with `async def complete(*, model, messages)`; covers valid JSON, code-fence stripping, retry-then-succeed, raise-after-two-failures).
- `tests/conftest.py` — mirror analyst's pattern: prepend `src` to `sys.path`, and override the root DB fixtures so `llm` tests need no DB.

## 5. Changes to `analyst`

- **Delete** `analyst/src/analyst/providers.py` (moved to `llm`).
- **`analyst/src/analyst/llm.py`** — reduced to the analyst-specific glue:
  ```python
  from typing import TypeVar
  from pydantic import BaseModel
  from llm.providers import attribution_headers, build_client
  from llm.structured import complete_structured
  from analyst.config import settings

  T = TypeVar("T", bound=BaseModel)

  async def complete_for_task(task, messages, schema):
      client = build_client(
          settings.analyst_llm_provider,
          settings.analyst_llm_api_key,
          settings.analyst_llm_base_url,
          settings.analyst_request_timeout_seconds,
          attribution_headers(settings.analyst_attribution_referer, settings.analyst_attribution_title),
      )
      return await complete_structured(client, settings.model_for(task), messages, schema)
  ```
  `analyze.py` / `recommend.py` keep importing `from analyst import llm` and calling `llm.complete_for_task(...)` — unchanged.
- **`analyst/config.py`** — unchanged (`AnalystSettings` stays in analyst).
- **`analyst/pyproject.toml`** — add `"llm"` to `dependencies` and `llm = { workspace = true }` to `[tool.uv.sources]`; remove the now-transitive `"openai>=1.40"` direct dep.
- **`analyst/tests/test_providers.py`** — removed (moved to `llm`).
- **`analyst/tests/test_llm.py`** — reduced to one wiring test: `complete_for_task` reads `AnalystSettings`, builds a client, and delegates to `complete_structured` (monkeypatch `analyst.llm.complete_structured` and `analyst.llm.build_client` to assert wiring + that `model_for(task)` is passed). No real network.
- **`analyst/tests/test_config.py`** — unchanged.

## 6. Workspace & build wiring

- Root `backend/pyproject.toml` `[tool.uv.sources]`: add `llm = { workspace = true }`. (Members glob `packages/*` already includes it.)
- Regenerate `uv.lock` (`uv lock`).
- `Dockerfile`:
  - `deps` stage: add `COPY packages/llm/pyproject.toml packages/llm/pyproject.toml` (before `uv sync`).
  - `api-build` stage: add `COPY packages/llm/src packages/llm/src` (alongside core/analyst/api src).
  - `api-dev` reload: add `--reload-dir /app/packages/llm/src`.
  - (pipeline-build does not yet need `llm` — SP2 adds it when labeling consumes it.)

## 7. Docs

- `CLAUDE.md`:
  - Modules table: add row `| `llm` | Shared LLM client: provider presets + structured output | openai SDK; imported by analyst (and labeling in SP2); no core dep |`.
  - Hard-rule note: change "Batch modules never import each other — share via `core`" to "...share via `core` (DB kernel) or `llm` (LLM client kernel)."
- `tech-stack.md`: note the `llm` shared package under the analyst/openai row.

## 8. Testing & verification

- `llm` suite green: `cd backend && ./.venv/bin/python -m pytest packages/llm/tests/ -v`.
- `analyst` suite green: `... packages/analyst/tests/ -v`.
- API analyst contract green: `... packages/api/tests/analyst/ -v` (run separately — analyst and api both define `tests/conftest.py`; a combined invocation raises pytest's ImportPathMismatchError).
- Behavior parity: the moved `providers.py` and `structured.py` are unchanged; the analyst path produces identical output.

## 9. Risks & mitigations

- **Module-name proximity:** `analyst.llm` (module) vs top-level `llm` (package). Absolute imports disambiguate (`from llm.providers import ...` resolves to the package; `analyst.llm` is its fully-qualified name). No runtime ambiguity.
- **uv.lock drift:** regenerate and commit `uv.lock` in the same change; CI/build uses `--frozen`.
- **api image dep surface:** `llm` adds only `openai` (already present in the api image via analyst) — no size impact.

## 10. Out of scope / deferred

- Embedding capability in `llm` (SP3).
- Any labeling change (SP2).
- Renaming `analyst.llm` to avoid proximity with the `llm` package (cosmetic; not worth the churn now).
