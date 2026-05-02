# CLAUDE.md

Internal dashboard surfacing topics worth writing for Tempo's editorial team. Backend: ingest competitor RSS + Tempo sitemap + Google Trends → cluster by topic → score → read-only API.

## Read first

`docs/README.md` lists the required reading order (8 files). Read them before any work. Do not invent context — `docs/constraints.md` lists every deferred feature.

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
| `pipeline`   | Daily orchestrator CLI             | imports all batch modules                  |

Rule: `api` never imports ML modules. Batch modules never import each other — share via `core`. Cross-module imports must be declared in `pyproject.toml`.

## Daily pipeline (06:00 WIB)

`ingest → embed → cluster → label → score`. Each step exposes `python -m <module>.cli run`. Full run: `python -m pipeline.cli run-daily`. Triggered by host cron.

## Reactive ingest daemon (D20)

`python -m ingest.cli serve` is a long-running process that LISTENs on `pg_notify('rss_source_created')` and fetches a single new source on demand. Runs alongside cron, not in place of it. Single replica only — the in-memory blocked-source map and immediate queue are process-local.

## API endpoints

Reads dominate; the only write surface is `ContentSource` CRUD (D19). Live: `/api/v1/clusters/morning`, `/api/v1/clusters/{id}`, `/api/v1/clusters/deferred`, `/api/v1/articles`, `/api/v1/sources` (GET/POST/PATCH/DELETE), `/api/v1/health`. Auth handled upstream.

## Schema

Source of truth: `backend/packages/core/src/core/models.py` (SQLAlchemy ORM). Documented mirror: `docs/schema.dbml`. Migrations via Alembic autogenerate, run from `backend/`.

## Hard rules (full list in `docs/constraints.md`)

- No microservices, message queue, Redis cache, separate vector DB, HNSW index, GraphQL, WebSockets, auth code. Writes are restricted to `content_source` CRUD (D19); every other table is read-only via the API.
- `vector(768)` is fixed; changing embedding model = migration + full re-embed.
- One embedding per article (`article_embedding.article_id` unique).
- GSC metrics are scoring inputs only — never returned via API.
- Trend keywords live in `trend_signal`, never in `article` columns.
- `source_type` enum: only `rss` and `internal` (no `trends`).
- src layout per package; no flat layouts.
- No comments explaining WHAT; only non-obvious WHY.
- No new top-level deps without updating `docs/tech-stack.md`.
- PRD §6 deferred features stay deferred.

## Quickstart

```bash
cd backend
cp .env.example .env
docker compose up -d postgres
uv sync
alembic upgrade head
```

- Module CLI: `uv run python -m <module>.cli run`
- API local: `uv run uvicorn api.main:app --reload --app-dir packages/api/src`
- Full pipeline: `uv run python -m pipeline.cli run-daily`

## Out of scope (other teams)

Auth, production deploy infra, frontend implementation, monitoring stack, internal GSC analytics dashboard.

## When unsure

Stop and re-read `docs/constraints.md` + `docs/decisions.md`. Ask before adding scope. The PRD is intentionally short — missing detail is not a gap.
