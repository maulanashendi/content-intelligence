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
| `embedding`  | Vectorize articles, 768d           | sentence-transformers, embeddinggemma-300m |
| `clustering` | UMAP → HDBSCAN                     | random_state pinned                        |
| `labeling`   | LLM cluster labels                 | transformers + Gemma 2B 4-bit              |
| `scoring`    | velocity, novelty, coverage        | sklearn, numpy                             |
| `api`        | FastAPI read-only                  | NO torch, NO ML imports                    |
| `pipeline`   | Long-running daemon (D24)          | reactive ingest+embed, scheduled cluster+label; imports all batch modules |
| `analyst`    | Editorial AI Analyst: article scoring + recommendation | openai SDK behind `providers.py` vendor boundary; switch vendor via `ANALYST_LLM_PROVIDER`; no ML import |

Rule: `api` never imports ML modules. Batch modules never import each other — share via `core`. Cross-module imports must be declared in `pyproject.toml`.

## Pipeline runtime (D24)

One supervised daemon, `python -m pipeline.cli serve`, owns every long-running concern. There is no host cron and no separate `ingest serve`.

- **Reactive ingest + embed (continuous).** The daemon polls all enabled RSS sources every 10 minutes (`POLL_INTERVAL=600`), runs the embed cycle inline after each ingest, and listens on `pg_notify('rss_source_created')` to fetch a single new source on demand.
- **Scheduled cluster + label + score (06:00 WIB daily).** An in-process `asyncio` scheduler emits `pg_notify('pipeline_cluster_label_score_requested')`; the same channel is used by the manual API trigger. Schedule is config-driven (`TIMEZONE`, `CLUSTER_SCHEDULE_HOUR`, `CLUSTER_SCHEDULE_MINUTE`). After clustering and labeling, `scoring.pipeline.run()` upserts raw signals into `cluster_insight` per D27 (supersedes D24's disabled clause). Signals: `tempo_covered`, `competitor_count`, `trend_match_count`, `trend_velocity`, `last_internal_days_ago`, `underperformed`.
- **Singleton.** In-memory immediate-fetch queue and the `pipeline_group_lock` row both assume a single replica.

Each batch step is also exposed as `python -m pipeline.cli <step>` for ad-hoc debugging (`ingest`, `embed`, `cluster`, `label`, `score`, `run-daily`); these are operator tools, not the production execution surface.

## Hardening track (post-MVP)

MVP is shipped. Post-MVP work is hardening, governed by four SOPs. Read the relevant one before changing code in that area:

- `docs/docker-sop.md` — Dockerfile, compose, image build and runtime rules
- `docs/logging-sop.md` — JSON logging contract, levels, request-ID propagation
- `docs/operations-sop.md` — running the stack in Docker, daemon supervision, recovery
- `docs/hardening-sop.md` — checklist for "harden feature X" tasks

## API endpoints

Reads dominate. Two write surfaces: `ContentSource` CRUD on `/api/v1/sources` (D19), and `POST /api/v1/pipeline/cluster-label-score` (D24, manual re-cluster — score is skipped). Live read endpoints: `/api/v1/clusters/morning`, `/api/v1/clusters/bento`, `/api/v1/clusters/{id}`, `/api/v1/clusters/{id}/volume-trend`, `/api/v1/clusters/deferred`, `/api/v1/articles`, `/api/v1/articles/volume-trend`, `/api/v1/sources` (GET), `/api/v1/pipeline/status`, `/api/v1/health`. Auth handled upstream. Stateless analyst endpoints (no DB writes): `POST /api/v1/analyst/analyze`, `POST /api/v1/analyst/analyze/batch`, `POST /api/v1/analyst/recommendation`.

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

- One-shot pipeline step: `docker compose --profile manual run --rm pipeline <step>` (`ingest`, `embed`, `cluster`, `label`, `score`, `run-daily`)
- Tests: `docker compose run --rm api pytest packages/<module>/tests/`
- Full operational reference: `docs/operations-sop.md`

## Out of scope (other teams)

Auth, production deploy infra, frontend implementation, monitoring stack, internal GSC analytics dashboard.

## When unsure

Stop and re-read `docs/constraints.md` + `docs/decisions.md`. Ask before adding scope. The PRD is intentionally short — missing detail is not a gap.
