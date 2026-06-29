# Embed the Editorial AI Analyst as a separate package

**Date:** 2026-06-18
**Status:** Draft — awaiting review
**Proposed decision:** D37 (see entry at the end of this doc)

## Goal

Fold the standalone **"Editorial AI Analyst"** app (currently `user-need/data-user-need-{backend,frontend}`) into content-intelligence so there is **one app** — one backend service, one frontend build — while keeping the analyst **completely separate** from content-intelligence's existing ingest → embed → cluster → label → score machinery.

The analyst today runs on the **OpenAI API**; content-intelligence runs **local** models. The merged app must let us **configure local vs API per task** via config.

## What the analyst does (ported source)

- **`/analyze`** — scores an article against 16 editorial features (`f01_breaking` … `f16_social_buzz`), runs a pure-Python rule engine over those features to rank the 8 "user need" categories (Update me, Educate me, Help me, …), and returns editorial feedback (headline suggestions, missing info, bias check, next angle).
- **`/analyze/batch`** — the same over a list of articles.
- **`/recommendation`** — a 2-stage pipeline: (1) extract filter parameters from a free-text intent, (2) generate 2–4 actionable insights + a summary over a filtered analytics dataset.
- A **chat / slash-command UI** that drives `/analyze` and `/recommendation`.

## Decisions captured (from brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| Scope | Which capabilities to embed | **All three**: article analysis, recommendation insights, chat/slash UI |
| Model switch | What the local/API switch governs | **Per-task config** (each analyst task independently local or API) |
| API provider | What "API" mode calls | **OpenAI-compatible** (one client; `base_url` + `key` + `model`) |
| Frontend | How the Next.js app is brought in | **Port into the Vite app** as a new `@ei-fe/*` feature using `@ei-fe/ui` |
| Local path | How "local" interactive requests are served | **API-only interactive** (no in-process model, no daemon dependency) |
| Separation | (added) The analyst is | **A new, self-contained package with its own pipeline**, not part of content-intelligence's daemon |

### Key consequence of these choices

Because "API" mode is an **OpenAI-compatible client** *and* interactive requests are **API-only**, the local/API distinction collapses to a **base-URL swap**:

- **API** = a hosted endpoint (OpenAI, a Claude-compatible gateway, etc.).
- **Local** = a local OpenAI-compatible server (Ollama / `llama.cpp --server` / vLLM).

The analyst therefore **never loads a model in-process**, **never imports torch/llama-cpp**, and **never touches the pipeline daemon**. content-intelligence's existing local Gemma labeling is left exactly as-is. The hard rule "`api` never imports ML" is preserved for free.

## Architecture

### Target shape

```
backend/packages/
  analyst/                       NEW — self-contained, depends on `core` only
    src/analyst/
      config.py                  AnalystSettings (reads same .env; analyst_* keys)
      llm.py                     OpenAI-compatible client + structured-output helper
      features.py                16-feature schema + system prompt
      category.py                pure-Python rule engine (ported verbatim)
      analyze.py                 run_analysis() / run_analysis_batch()
      recommend.py               2-stage recommendation pipeline + data loader
      schemas.py                 request/response Pydantic models
      data/airflow_data.json     ported analytics dataset (static, on-demand load)
    tests/
  api/
    src/api/routes/analyst.py    NEW route module — imports `analyst`, no ML
  core/                          unchanged
  labeling/ embedding/ ...       unchanged

frontend/packages/
  features/src/analyst/          NEW feature: analyze + recommendation + chat views
  ui/                            existing @ei-fe/ui primitives (re-skin shadcn cards)
  api/                           regenerated client (picks up new endpoints)
  app/                           new route + nav entry
```

### Module boundaries (isolation)

- **`analyst` depends only on `core`** (config, logging). It does **not** import `ingest`, `embedding`, `clustering`, `labeling`, `scoring`, or `pipeline`, and none of them import it. This is enforced by `pyproject.toml` workspace deps (D1 rule).
- **`api` imports `analyst`** for the route handlers. This is safe: `analyst` pulls only an HTTP LLM client (no torch/ML), so "`api` never imports ML" still holds.
- The analyst owns **its own LLM client** (`analyst/llm.py`). It does **not** reuse `labeling/llm.py`, and `labeling` is not modified. (Unifying both onto one client later is possible but explicitly out of scope.)

### Pipeline separation

- content-intelligence's **D24 pipeline daemon is untouched** and the analyst has no part in it.
- The analyst is **request/response only** — no long-running process, no scheduler, no `pg_notify` channel.
- `/recommendation` reads a **static analytics dataset** (`analyst/data/airflow_data.json`, ported as-is) loaded on demand. Periodic refresh of that dataset is **out of scope**; if needed later it is the analyst's own concern, never the content-intelligence daemon.

### The model abstraction (`analyst/llm.py`)

A thin client and one structured-output helper:

- Built on the **`openai` SDK** pointed at `analyst_llm_base_url` (works against any OpenAI-compatible server). `httpx`-only is the zero-new-dep alternative if we want to avoid adding `openai`.
- Calls use **`chat.completions` with `response_format` = JSON schema** (portable across OpenAI and most compatible servers) rather than OpenAI's newer `responses.parse` — the original code's `responses.parse` and LangChain `with_structured_output` are both dropped.
- A helper `complete_structured(messages, schema_model) -> schema_model` validates the reply into a Pydantic model and retries once on invalid JSON.
- **Per-task** resolution: `analyze` and `recommendation` each read their own provider/model so they can differ (e.g. analyze on a hosted model, recommendation on a local server).

### `/recommendation` — drop LangChain

The 2-stage pipeline is reimplemented directly on `analyst/llm.py`:

1. **Extract filters** — structured output into `DataFilterParameters` (ported schema).
2. **Filter the dataset** — the existing pure-Python `_apply_filters` (ported verbatim).
3. **Generate insights** — structured output into `RecommendationOutput`.

This removes the `langchain`, `langchain-openai`, and `google-cloud-bigquery` dependencies entirely. Live BigQuery is deferred; the ported JSON dataset stands in for it (the original already ran on the JSON, not live BigQuery).

### API surface

New route module `api/routes/analyst.py` mounted under `/api/v1/analyst`:

| Method | Path | Body | Response model |
|--------|------|------|----------------|
| POST | `/api/v1/analyst/analyze` | `{title, content}` | `AnalyzeResponse` |
| POST | `/api/v1/analyst/analyze/batch` | `{articles: [...]}` | `list[AnalyzeResponse]` |
| POST | `/api/v1/analyst/recommendation` | `{intent}` | `RecommendationResponse` |
| POST | `/api/v1/analyst/chat` *(optional — see note)* | `{message}` | routes to analyze/recommendation (slash dispatch) |

Each endpoint follows the repo's OpenAPI contract rule: Pydantic `response_model=`, explicit status code, one-line summary. **Auth and rate limiting are dropped** — content-intelligence handles auth upstream (the ported `slowapi` + bearer + CORS + Mangum/Lambda code is not carried over).

> Open question for review: whether `/chat` is a real endpoint or whether slash-dispatch happens client-side, calling `/analyze` or `/recommendation` directly. Default below assumes **client-side dispatch** (no `/chat` endpoint) for simplicity.

### Configuration (`analyst/config.py`)

```python
class AnalystSettings(BaseSettings):
    # OpenAI-compatible endpoint ("local" = a local server URL; "api" = hosted)
    analyst_llm_base_url: str = "https://api.openai.com/v1"
    analyst_llm_api_key: str = ""
    # per-task model selection
    analyst_analyze_model: str = "gpt-4o"
    analyst_recommend_model: str = "gpt-4o"
    # optional per-task base-url override (falls back to analyst_llm_base_url)
    analyst_analyze_base_url: str = ""
    analyst_recommend_base_url: str = ""
    analyst_request_timeout_seconds: int = 60
```

Switching a task to a local model is purely: point its `*_base_url` at the local server and set its `*_model`. No code path changes.

### Frontend

- New feature package area `frontend/packages/features/src/analyst/`:
  - `analyze-view.tsx` — paste an article → 16-feature grid + user-need ranking + editorial feedback.
  - `recommendation-view.tsx` — intent input → insights + summary + sample-data table.
  - `analyst-chat.tsx` — the chat/slash surface.
- Components are rebuilt on **`@ei-fe/ui` primitives + Tailwind** (the shadcn `MetricCard`, `RecommendationCard`, `chat-bot`, charts are re-skinned). **No shadcn/Radix is introduced** — repo rule: new components use `@ei-fe/ui` only.
- Data fetching uses the **regenerated `@ei-fe/api`** client (openapi-typescript + react-query) after the new endpoints land; no hand-rolled `fetch`/server actions.
- A nav entry + route is added in `@ei-fe/app`. Cross-feature imports stay forbidden; anything genuinely shared promotes to `@ei-fe/ui`.

## Data flow

```
Analyze:   FE analyze-view ──POST /api/v1/analyst/analyze──▶ api route
           ──▶ analyst.analyze.run_analysis()
               ├─ analyst.llm.complete_structured() ──▶ OpenAI-compatible endpoint
               └─ analyst.category.rank_user_needs()  (pure Python)
           ◀── features + user_needs + feedback

Recommend: FE recommendation-view ──POST /recommendation──▶ api route
           ──▶ analyst.recommend.run_recommendation()
               ├─ llm: extract filters ──▶ endpoint
               ├─ load + filter analyst/data/airflow_data.json (pure Python)
               └─ llm: generate insights ──▶ endpoint
           ◀── filters + sample_data + insights + summary
```

## Dependencies & docs

- New backend deps in `analyst/pyproject.toml`: `openai` (or `httpx` only), `pydantic`, `pydantic-settings`, `core`. **`docs/tech-stack.md` updated** in the same PR (repo rule).
- **Removed vs the original**: `langchain`, `langchain-openai`, `google-cloud-bigquery`, `slowapi`, `mangum`, `beautifulsoup4`, `tqdm`.
- No Alembic migration: the analyst has **no tables** initially (recommendation reads a file). Persisting analyses is a separate future decision.

## Testing

- `category.py` — port the existing rule-engine tests; pure functions, no mocks.
- `analyze.py` / `recommend.py` — unit tests with a **faked LLM client** (no network) asserting prompt assembly, schema validation, and the filter logic.
- `api/routes/analyst.py` — FastAPI `TestClient` tests with the analyst layer mocked.
- Frontend — component tests for the views against fixture responses (mirrors the existing demo fixture approach).

## Deferred (YAGNI)

LangChain, live BigQuery, AWS Lambda / Mangum, `slowapi` rate limiting, in-app bearer auth, in-process local model for the analyst, persisting analyses to Postgres, scheduled dataset refresh, unifying `labeling` onto the analyst LLM client.

## Open questions for review

1. **Package name** — `analyst` (placeholder). Alternatives: `editorial`, `userneeds`. Pick one before implementation.
2. **`/chat` endpoint vs client-side slash dispatch** — default is client-side; confirm.
3. **Default provider** — ship defaulting to a hosted OpenAI-compatible endpoint, or default `analyst_llm_base_url` to a local server so it works offline out of the box?

## Proposed decision-log entry

```markdown
## D37. Embed the Editorial AI Analyst as a separate, API-backed package

**Context.** A standalone "Editorial AI Analyst" app (OpenAI-backed FastAPI + Next.js)
must merge into content-intelligence as one app, without entangling its existing
local-ML pipeline.

**Options considered.**
- Weave analyze/recommendation into existing modules + the pipeline daemon
- New self-contained `analyst` package, API-backed, separate from the daemon
- Keep two apps behind a reverse proxy

**Decision.** New self-contained `analyst` package. Interactive analyze/recommendation
are served via an OpenAI-compatible client (local = local-server base URL, API = hosted).
No in-process model, no daemon involvement. Frontend ported into the Vite app as a new
`@ei-fe/*` feature. LangChain/BigQuery/Lambda/slowapi dropped.

**Rationale.** Preserves "`api` never imports ML", keeps the daemon a singleton owning
only the clustering pipeline, and reduces the local/API switch to a base-URL swap.

**Implication.** The analyst has its own config block and no DB tables initially.
Unifying `labeling` onto the same client, persistence, and live BigQuery are future work.
```
