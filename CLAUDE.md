# CLAUDE.md

Internal dashboard surfacing topics worth writing for Tempo's editorial team. Backend: ingest competitor RSS + Tempo sitemap + Google Trends → cluster by topic → score → read-only API.

## Read first

`docs/README.md` is the entry point. It names the four core docs to read before writing code (`prd.md`, `architecture.md`, `constraints.md`, `schema.dbml`) and routes every other doc by task. Do not invent context — `docs/constraints.md` lists every deferred feature.

## Layout

```
docs/         spec + architecture + decisions
backend/      all Python code (uv workspace)
frontend/     frontend (vite, bun, tailwind)
```

All backend commands run from `backend/`.

## Modules (`backend/packages/`)

| Module       | Purpose                            | Notes                                      |
| ------------ | ---------------------------------- | ------------------------------------------ |
| `core`       | Models, async DB session, settings | Imported by all others                     |
| `ingest`     | RSS + sitemap + Trends RSS         | feedparser, httpx                          |
| `embedding`  | Vectorize articles, 768d           | API default (`text-embedding-3-large` via OpenRouter, shared `llm`); local opt-in (`embeddinggemma-300m`, torch). `EMBEDDING_PROVIDER=api (default)\|local` |
| `clustering` | UMAP → HDBSCAN                     | random_state pinned; always on-box         |
| `labeling`   | LLM cluster labels + desk/user-need classification | API default (`gpt-4o-mini` via OpenRouter, shared `llm`); local opt-in (Gemma 2B GGUF). `LABELING_PROVIDER=api (default)\|local` |
| `scoring`    | demand × performance → editorial quadrant (D35) | sklearn, numpy; always on-box       |
| `api`        | FastAPI read-only                  | NO torch, NO ML imports                    |
| `pipeline`   | Long-running daemon (D24)          | reactive ingest+embed, scheduled cluster+score+label; imports all batch modules |
| `llm`        | Shared LLM client kernel: provider presets + structured output | openai SDK; imported by `embedding`, `labeling`, `analyst`; no `core` dep |
| `analyst`    | Editorial AI Analyst: article scoring + recommendation | uses shared `llm` package; switch vendor via `ANALYST_LLM_PROVIDER`; no ML import |

Rule: `api` never imports ML modules. Batch modules never import each other — share via `core` (DB kernel) or `llm` (LLM client kernel). Cross-module imports must be declared in `pyproject.toml`.

## Pipeline runtime (D24)

One supervised daemon, `python -m pipeline.cli serve`, owns every long-running concern. There is no host cron and no separate `ingest serve`.

- **Reactive ingest + embed (continuous).** The daemon polls all enabled RSS sources every 10 minutes (`POLL_INTERVAL=600`), runs the embed cycle inline after each ingest, and listens on `pg_notify('rss_source_created')` to fetch a single new source on demand. Embedding and labeling default to the API path (`EMBEDDING_PROVIDER=api`, `LABELING_PROVIDER=api`); the local on-box path (torch/Gemma) is an opt-in build that requires the `pipeline-local` image.
- **Scheduled cluster + score + label (06:00 WIB daily).** An in-process `asyncio` scheduler emits `pg_notify('pipeline_cluster_label_score_requested')`; the same channel is used by the manual API trigger. Schedule is config-driven (`TIMEZONE`, `CLUSTER_SCHEDULE_HOUR`, `CLUSTER_SCHEDULE_MINUTE`). The run executes in order: **cluster → score → label → prune**. `scoring.pipeline.run()` (active per D27, redesigned by D35) upserts `cluster_insight` with demand × performance signals and the derived `editorial_quadrant`; labeling then writes labels + desk/user-need classification.
- **Singleton.** In-memory immediate-fetch queue and the `pipeline_group_lock` row both assume a single replica.

Each batch step is also exposed as `python -m pipeline.cli <step>` for ad-hoc debugging (`ingest`, `embed`, `cluster`, `label`, `score`, `run-daily`); these are operator tools, not the production execution surface.

## Hardening track (post-MVP)

MVP is shipped. Post-MVP work is hardening, governed by four SOPs. Read the relevant one before changing code in that area:

- `docs/docker-sop.md` — Dockerfile, compose, image build and runtime rules
- `docs/logging-sop.md` — JSON logging contract, levels, request-ID propagation
- `docs/operations-sop.md` — running the stack in Docker, daemon supervision, recovery
- `docs/hardening-sop.md` — checklist for "harden feature X" tasks

## API endpoints

Reads dominate; `/openapi.json` (live at `/docs`) is the contract. Two write surfaces: `ContentSource` CRUD on `/api/v1/sources` (D19), and `POST /api/v1/pipeline/cluster-label-score` (D24, manual re-run — runs the full cluster + score + label path, same as the scheduled run). Read endpoints under `/api/v1`: `clusters/{morning,bento,deferred,quadrant-summary,quadrant/{q},runs/latest,current}`, `clusters/{id}`, `clusters/{id}/volume-trend`, `articles`, `articles/volume-trend`, `trend-signals/latest`, `sources` (GET), `pipeline/status`, `health`. Auth handled upstream. Stateless analyst endpoints (no DB writes): `POST /api/v1/analyst/{analyze,analyze/batch,recommendation}`. The four `clusters/{morning,bento,quadrant-summary,quadrant/{q}}` endpoints accept a `dna` toggle (D39) that hard-filters to clusters whose `desk_category` ∈ `morning_allowed_desks` AND `user_need_category` ∉ `morning_denied_user_needs` (classification written by the labeling step); on for `/morning` by default.

## Schema

Source of truth: `backend/packages/core/src/core/models.py` (SQLAlchemy ORM). Documented mirror: `docs/schema.dbml`. Migrations via Alembic autogenerate, run from `backend/`.

## Hard rules (full list in `docs/constraints.md`)

- No microservices, message queue, Redis cache, separate vector DB, HNSW index, GraphQL, WebSockets, auth code. No standalone scheduler library (APScheduler, Prefect, Dagster) and no host `cron` — scheduling lives inside `pipeline-daemon` as plain `asyncio` tasks (D24). Writes are restricted to `content_source` CRUD (D19) and the manual cluster trigger (D24); every other table is read-only via the API.
- `vector(768)` is fixed; changing embedding model = migration + full re-embed.
- One embedding per article (`article_embedding.article_id` unique).
- GSC metrics are scoring inputs only — never returned via API, **except** aggregated per-cluster clicks exposed as `views` on `/clusters/bento` (D38). Impressions/CTR/position stay internal.
- Trend keywords live in `trend_signal`, never in `article` columns.
- `source_type` enum: only `rss` and `internal` (no `trends`).
- src layout per package; no flat layouts.
- Frontend layering: see `docs/architecture.md` §Frontend (shape) and `docs/frontend.md` (rules). Cross-feature imports forbidden; a component used by ≥2 features promotes to `@ei-fe/ui`. New components never use legacy global CSS classes (`.card`, `.kw-row`) — Tailwind + a `@ei-fe/ui` primitive only.
- No comments explaining WHAT; only non-obvious WHY.
- No new top-level deps without updating `docs/tech-stack.md`.
- PRD §6 deferred features stay deferred.
- Local dev runs in Docker (`docker compose` from `backend/`), not host `uv run`. Host `uv run` is allowed only for unit tests and IDE integration. See `docs/operations-sop.md`.
- All logs are JSON to stdout via `core.logging.configure_logging()`. No `print()`. New entry points call `configure_logging()` once. See `docs/logging-sop.md`.
- API contract is FastAPI's `/openapi.json` (live at `/docs`), generated from Pydantic models + `response_model=` + route summaries. Endpoint changes update the Pydantic schema, `response_model=`, status code, and one-line summary in the same commit. There is no separate Markdown contract. Cross-cutting API rules: `docs/conventions.md` §API endpoints.
- Hardening work follows `docs/hardening-sop.md`. PR title `harden(<module>): ...` and the checklist table are required.

## Quickstart

```bash
cd backend
cp .env.example .env
docker compose up -d postgres
docker compose run --rm api alembic upgrade head
docker compose up -d
docker compose logs -f api
```

- One-shot pipeline step: `docker compose --profile manual run --rm pipeline <step>` (`ingest`, `embed`, `cluster`, `label`, `score`, `run-daily`, `reembed`) — the manual profile uses the `pipeline-api` image (no torch/Gemma).
- Tests: `docker compose run --rm api pytest packages/<module>/tests/`
- Full operational reference: `docs/operations-sop.md`

## Out of scope (other teams)

Auth, production deploy infra (orchestration/scaling/secrets beyond compose), frontend hosting/serving config (gateway, nginx, cache headers, SPA fallback), monitoring stack, and the separate internal GSC analytics dashboard. The frontend SPA **itself** lives in `frontend/` and is in scope — see `docs/frontend.md`.

## When unsure

Stop and re-read `docs/constraints.md` + `docs/decisions.md`. Ask before adding scope. The PRD is intentionally short — missing detail is not a gap.
