# Architecture

This document describes the high-level structure of Editor Intelligence: how modules are organized, how they depend on each other, how data flows through the system, and which processes run when.

## Philosophy

**Modular monorepo, not microservices.** A single git repository contains multiple Python packages that depend on each other through declared interfaces. Each package can be developed, tested, and (when needed) packaged independently, but lives in the same source tree.

**Long-running daemon, not OS cron.** The pipeline orchestrator runs as a singleton daemon. Reactive triggers (`pg_notify`) drive the ingest + embed chain on demand; an in-process scheduler fires the heavier cluster + label + score run once per day at 06:00 WIB. The product needs are still inherently daily for clustering, but the scheduler now lives in Python — there is no host `cron`, no `systemd` timer, no separate job system. A queue system (Celery, RabbitMQ, Redis Streams) remains rejected: it would add operational surface without delivering value at this scale.

**Single embedding model active at a time.** Switching the embedding model is a deliberate event that requires a schema migration and a full re-embed of all articles. Multi-model serving is not supported.

**Hosted AI by default, on-box weights as an opt-in.** Embedding, cluster labeling, and the editorial analyst run through a hosted, OpenAI-compatible API (OpenRouter by default), reached through the shared `llm` package. This is what keeps the production footprint inside a ~2 GB VPS: no `torch`, no GGUF weights, no GPU. The on-box path (`sentence-transformers` for embedding, `llama-cpp` Gemma for labeling) still exists behind provider switches (`EMBEDDING_PROVIDER`, `LABELING_PROVIDER`) but requires the heavier `pipeline-local` image. Heavy libraries are lazy-imported so they never load on the API path. Only classical ML — UMAP/HDBSCAN clustering and sklearn/numpy scoring — always runs on-box. See `docs/llm-models.md` for the model inventory and vendor-switching steps.

**Read-dominant API with two narrow write surfaces.** The API exposes `POST/PATCH/DELETE` on `/api/v1/sources` so editors can manage RSS feeds at runtime, and `POST /api/v1/pipeline/cluster-label-score` so editors can request an on-demand re-clustering. Every other table — articles, clusters, embeddings, GSC metrics, trend signals — is read-only via the API. User actions on cluster/article rows (claim, dismiss, etc.) remain out of scope per PRD Section 6.

**Docker compose is the runtime, dev to prod.** Both local development and production run via `docker compose` from `backend/`. The same Dockerfile produces the same images in both environments; only the compose overlay differs (`docker-compose.yml` for dev with bind mounts and live reload, `docker-compose.prod.yml` for prod with `restart: always`, rotated `json-file` logs, and Postgres kept off the host network). Host `uv run` is reserved for unit tests and IDE integration. Operational details live in `docs/docker-sop.md` and `docs/operations-sop.md`.

## Process topology

Three long-running concerns, plus the database:

| Process           | Lifecycle                 | Trigger                                                                                                                                                       |
| ----------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api`             | Always running            | HTTP requests from the frontend                                                                                                                               |
| `pipeline-daemon` | Always running, singleton | `pg_notify('rss_source_created')`, `pg_notify('pipeline_cluster_label_score_requested')`, in-process ingest poll loop, in-process scheduler tick at 06:00 WIB |
| `postgres`        | Always running            | Hosts pgvector data                                                                                                                                           |

The previous split between `ingest serve` and `pipeline serve` is collapsed into one supervised process (`python -m pipeline.cli serve`). It owns every long-running concern: reacting to new RSS sources, periodic ingest polling with reactive embed chaining, the daily scheduled cluster + label run, and the manual cluster + label trigger. Single replica only — concurrency is governed by DB lock rows in `pipeline_group_lock`, but the in-memory blocked-source map and immediate-fetch queue are process-local.

Operational details — compose service names, image targets, command, supervision, recovery — live in `docs/operations-sop.md` §Service map. The daemon must run as a singleton in both dev and prod compose stacks. In dev, `postgres` runs as a compose service; in the lean 2 GB prod topology it is external (supplied via `DATABASE_URL`), not co-located.

The frontend lives in `frontend/` and is built with Bun + Vite. In dev it is part of the same compose stack; production hosting is owned by the deploy team.

## Modules

All backend code lives under `backend/`. The codebase is organized as a `uv` workspace under `backend/packages/`. Each module is an installable Python package with its own `pyproject.toml`.

| Module       | Responsibility                                                                        | Depends on                         |
| ------------ | ------------------------------------------------------------------------------------- | ---------------------------------- |
| `core`       | Shared kernel: SQLAlchemy models, async DB session, Pydantic settings, common types   | (none)                             |
| `ingest`     | Fetch and persist articles from competitor RSS, Tempo sitemap, Google Trends RSS, GSC | `core`                             |
| `embedding`  | Generate 768d dense vectors for articles (hosted API by default; on-box opt-in)       | `core`, `llm`                      |
| `clustering` | Reduce dimensionality (UMAP) and cluster articles (HDBSCAN) into topics — on-box      | `core`                             |
| `labeling`   | Generate human-readable cluster labels (hosted LLM by default; on-box Gemma opt-in)   | `core`, `llm`                      |
| `scoring`    | Compute demand, performance, and the editorial quadrant per cluster — on-box          | `core`                             |
| `llm`        | Shared LLM client kernel: provider presets + structured output (no `core` dependency) | (none)                             |
| `analyst`    | Editorial AI analyst: article scoring + recommendations via the hosted LLM            | `core`, `llm`                      |
| `api`        | FastAPI HTTP layer serving the dashboard endpoints and the two write surfaces         | `core`, `analyst`                  |
| `pipeline`   | Long-running daemon driving reactive ingest + embed and scheduled cluster+label+score | `core` plus the five batch modules |

The `scoring` module is **active** in the daemon's run path (re-enabled by D27, redesigned by D35). After clustering and labeling, the daemon invokes `scoring.pipeline.run`, which upserts per-cluster signals into `cluster_insight`: `demand_score` / `high_demand`, `performance_level`, and the derived `editorial_quadrant` (`opportunity`, `winning`, `evergreen`, `ignore`, `too_early`). Scoring runs on-box (scikit-learn, numpy); it makes no API calls. Raw GSC numbers are stored as internal scoring inputs and never returned via the API — only the derived editorial levels are surfaced.

### Dependency graph

```
ingest ────┐
clustering─┼──────────────> core
scoring ───┘

embedding ─┐
labeling ──┼──> core, llm        (llm is a leaf — no core dependency)
analyst ───┘

pipeline ──> ingest, embedding, clustering, labeling, scoring ──> core
api      ──> analyst ──> core, llm
```

`api` is intentionally lean. It does NOT import any ML module and never runs on-box inference; it reads pre-computed data from the database and owns two write surfaces (`content_source` and `pipeline_group_lock`). It does make outbound calls to the hosted LLM, but only for the stateless analyst endpoints (no DB writes), through the shared `llm` package — no model weights are loaded in-process. This keeps the API container small (~200–500 MB) and free of torch/GGUF dependencies.

The `llm` package is a leaf with no dependency on `core`: it is a pure client kernel (provider presets + structured output) shared by `embedding`, `labeling`, and `analyst`. This is the seam that lets inference move off-box without touching the batch modules' own logic.

Batch modules do not import each other. Shared logic between them lives in `core`. This rule prevents accidental coupling and keeps each module testable in isolation.

## Pipeline flow

The daemon runs three concurrent concerns inside a single Python process. All three converge on the same downstream effect — articles flowing through ingest, embedding, and (eventually) clustering — but each has its own trigger.

### Reactive ingest + embed (continuous)

```
pg_notify('rss_source_created', <id>)
  │
  ▼
pipeline-daemon: fetch single source immediately

ingest poll loop (every N minutes)
  │
  ▼
ingest cycle complete
  │
  ▼
embed cycle runs in the same daemon (no API call, no manual step)
  │
  ▼
article_embedding rows ready for the next cluster run
```

There is no manual ingest + embed trigger. New articles flow into the database and become embedded without any operator action. The previous `POST /api/v1/pipeline/ingest-embed` endpoint has been removed.

### Scheduled cluster + score + label (06:00 WIB daily)

The daemon's internal scheduler emits `pg_notify('pipeline_cluster_label_score_requested')` once per day at 06:00 WIB. The same channel is used by the manual API trigger below — there is exactly one execution path. The steps run **in order: cluster → score → label → prune** (scoring runs before labeling — it is cheap SQL/numpy and does not depend on labels).

```
06:00 WIB internal scheduler tick
  │
  ▼
pipeline-daemon: acquire DB lock on group=cluster_label_score
  │
  ▼
Cluster
  - Load embeddings from the last 7 days
  - UMAP reduce 768 -> 30 dimensions (random_state=42 for stability)
  - HDBSCAN cluster
  - Mark all previous article_cluster.is_current = false
  - Insert new cluster_run, article_cluster, article_cluster_member rows

Score (active — D27/D35)
  - Compute per-cluster demand_score / high_demand, performance_level,
    and the derived editorial_quadrant (on-box: scikit-learn, numpy).
  - Upsert signals into cluster_insight. Raw GSC numbers stay internal.

Label
  - For each (top-N) cluster: pick top 3-5 articles by relevance
  - Format prompt with title + first_paragraph
  - Generate label + desk/user-need classification via the hosted LLM
    (default: OpenRouter gpt-4o-mini, structured JSON). On-box Gemma 2 2B
    GGUF is the opt-in local path.
  - Update article_cluster.label and cluster_insight classification fields

Prune (D33)
  - Drop cluster runs beyond the retention window (ON DELETE CASCADE)
  │
  ▼
mark cluster_run.finished_at (D36), release DB lock
```

The cluster window is 7 days (down from the previous 30) to keep topics tied to the current week's news cycle. Scheduler interval, time-of-day, and timezone are config-driven via `core.config.settings`; the default is 06:00 WIB to preserve the morning-view contract.

### Manual cluster trigger (on demand)

```
POST /api/v1/pipeline/cluster-label-score
  │
  ▼
api: check pipeline_group_lock; if free, INSERT lock row + pg_notify
  │
  ▼
pipeline-daemon: same code path as the scheduled run
```

The endpoint name keeps `cluster-label-score` for FE compatibility; request body and response shape are unchanged. Inside the daemon, the run executes the full path — cluster, score, label, prune — identical to the scheduled run.

### CLI entry points (debugging only)

Each step is also exposed as a standalone CLI command for manual debugging or partial re-runs from inside the container:

```
docker compose --profile manual run --rm pipeline ingest
docker compose --profile manual run --rm pipeline embed
docker compose --profile manual run --rm pipeline cluster
docker compose --profile manual run --rm pipeline label
docker compose --profile manual run --rm pipeline score   # part of the daily daemon path; exposed here for ad-hoc re-runs
```

These are operator tools. The supervised daemon is the production execution surface.

## API surface

These endpoints serve the dashboard. Authentication is handled by an upstream gateway (out of scope for this codebase).

| Method   | Path                                   | Purpose                                            |
| -------- | -------------------------------------- | -------------------------------------------------- |
| `GET`    | `/api/v1/clusters/morning`              | Opportunity clusters ranked by demand × performance |
| `GET`    | `/api/v1/clusters/bento`                | All current clusters, ranked + paginated (bento grid) |
| `GET`    | `/api/v1/clusters/quadrant/{quadrant}`  | Top clusters in one editorial quadrant             |
| `GET`    | `/api/v1/clusters/quadrant-summary`     | Quadrant distribution across current clusters      |
| `GET`    | `/api/v1/clusters/deferred`             | High-demand, uncovered, stale-coverage topics      |
| `GET`    | `/api/v1/clusters/runs/latest`          | Metadata for the most recent finished cluster run  |
| `GET`    | `/api/v1/clusters/current`              | Current run's clusters (lightweight list)          |
| `GET`    | `/api/v1/clusters/{cluster_id}`         | Cluster detail with member articles                |
| `GET`    | `/api/v1/clusters/{cluster_id}/volume-trend` | Competitor vs internal volume per WIB bucket  |
| `GET`    | `/api/v1/articles`                      | Paginated list of all ingested articles            |
| `GET`    | `/api/v1/articles/volume-trend`         | Article volume per WIB bucket, split by source type |
| `GET`    | `/api/v1/sources`                       | List all content sources                           |
| `POST`   | `/api/v1/sources`                       | Add a new RSS source                               |
| `PATCH`  | `/api/v1/sources/{id}`                  | Toggle a source on or off                          |
| `DELETE` | `/api/v1/sources/{id}`                  | Hard delete a source with no articles              |
| `POST`   | `/api/v1/pipeline/cluster-label-score`  | Manual re-run trigger (cluster + score + label + prune) |
| `POST`   | `/api/v1/pipeline/analysis`             | Manual analysis-step trigger (D29)                 |
| `GET`    | `/api/v1/pipeline/status`               | Pipeline run status                                |
| `POST`   | `/api/v1/analyst/analyze` · `/analyze/batch` · `/recommendation` | Stateless editorial analyst (no DB writes) |
| `GET`    | `/api/v1/trend-signals/latest`          | Latest trending keywords                           |
| `GET`    | `/api/v1/health`                        | DB connectivity check                              |

All cluster, article, and trend-signal endpoints are read-only. The `dna` query param (D39) toggles the desk/user-need filter on `clusters/{morning,bento,quadrant-summary,quadrant/{q}}` (default on for `/morning`, off for the other three). The only surface that writes a data table is:

- `/api/v1/sources` (POST/PATCH/DELETE) — runtime feed management. POST emits `pg_notify('rss_source_created', <id>)`; the daemon consumes that channel and ingests the new feed within minutes.

The pipeline trigger endpoints (`POST /pipeline/cluster-label-score`, `POST /pipeline/analysis`, D29) write only a `pipeline_group_lock` row and emit a `pg_notify`; they touch no analytical table and return 409 if the lock is held.

The previous `POST /api/v1/pipeline/ingest-embed` is removed. Ingest + embed is fully reactive and needs no operator trigger.

## Frontend

The dashboard SPA lives in `frontend/` (Bun + Vite + React + Tailwind v4) and consumes the API surface above. It never talks to the database, the daemon, or any model directly.

**Modular monorepo, mirroring the backend.** A single workspace under `frontend/packages/` with five packages, each an installable workspace member with explicit cross-package dependencies declared in `package.json`.

| Layer   | Package           | Responsibility                                                            |
| ------- | ----------------- | ------------------------------------------------------------------------- |
| Shell   | `@ei-fe/app`      | Vite SPA entry, providers, router, route shells                           |
| Compose | `@ei-fe/features` | Per-route views composed from `ui` primitives and `api` hooks             |
| Atoms   | `@ei-fe/ui`       | shadcn primitives, layout, state components, icons, Tailwind preset       |
| Data    | `@ei-fe/api`      | fetch wrapper, generated OpenAPI types, Zod schemas, TanStack Query hooks |
| Kernel  | `@ei-fe/core`     | env validation, design tokens, domain types, formatters, error class      |

### Dependency graph

```
app
 │
 ▼
features ──► ui ──┐
 │                ├──► core
 └──► api ────────┘
```

Three rules govern composition:

- `ui` never imports `api`; `api` never imports `ui`. UI primitives are presentational; the data layer knows no DOM.
- Features never import other features. Shared visuals lift to `@ei-fe/ui`; shared logic lifts to `@ei-fe/core`.
- A component used by ≥2 features is promoted out of its feature folder. Single-use components stay where they were born — premature promotion creates abstractions that may not survive the second use case.

Routes are thin: read URL params, call the query hook, render the feature view. Logic in routes is a smell — lift it to `features` or `core`.

This section sets the shape. Operational rules — package responsibilities in detail, naming, codegen workflow, styling priority, testing — live in `docs/frontend.md`.

## Data store

A single PostgreSQL 16 instance with the pgvector 0.7+ extension.

- Articles, embeddings, clusters, trend signals, and insights all live in Postgres.
- Vectors are stored in `vector(768)` columns matching the active embedding model.
- No HNSW or IVFFlat index in MVP. The happy path does no similarity search; indexes are added only when a feature requires them.
- On the default API inference path no model weights are loaded, so no model cache is needed. On the opt-in on-box path (`pipeline-local` image), HuggingFace and llama-cpp caches live under `HF_HOME` and are mounted as a Docker volume to persist across restarts.
- `pipeline_group_lock` is the single source of truth for "a pipeline group is currently running." The API checks it before issuing `pg_notify`; the daemon writes/deletes rows around runs.

There is no separate vector database, no Redis cache, and no message broker. Adding any of these requires a documented decision in `decisions.md`.

## Runtime: Docker compose, dev to prod

Both environments run via `docker compose` from `backend/`:

- **Dev.** `docker compose up -d` brings up `postgres`, `api`, and `pipeline-daemon`. Source is bind-mounted; reload is live. Frontend is run from `frontend/` with `bun run dev` and points at the compose API. Host `uv run` is reserved for unit tests and IDE integration.
- **Prod.** `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` runs the **lean 2 GB topology**: just `api`, `pipeline-daemon`, and the manual-profile `pipeline` — **Postgres is external** (managed off-box, supplied via `DATABASE_URL`), not co-located. The daemon builds the slim `pipeline-api` image (no torch, no Gemma), with `EMBEDDING_PROVIDER`/`LABELING_PROVIDER` defaulting to `api`; `mem_limit` is ~512 MB for `api` and ~1 GB for the daemon. Prod drops bind mounts, applies `restart: always`, binds the API behind a reverse proxy, and rotates `json-file` logs. Required env (`DATABASE_URL`, the OpenRouter API keys, etc.) comes from `backend/.env.prod` (gitignored); the stack refuses to start without it.

Image rebuilds rely on Docker layer cache. The default `pipeline-api` image carries no ML weights; the heavier `pipeline-local` image (torch + llama-cpp Gemma) is opt-in for the on-box inference path. Full operational reference — image targets, healthchecks, the API⇄local switch, recovery procedures — lives in `docs/docker-sop.md` and `docs/operations-sop.md`.

## Out of this codebase

These exist or will exist for the product but are NOT implemented here:

- **Authentication and identity.** Handled by an upstream gateway by another team.
- **Production deployment infrastructure beyond docker compose.** Image build and compose composition are described in `docs/docker-sop.md`; runtime supervision in `docs/operations-sop.md`. Production orchestration beyond compose (Kubernetes, scaling, secret distribution) is owned by the deploy team.
- **Production hosting / serving config.** `bun run build` outputs static assets; the deploy team owns gateway, nginx, cache headers, and SPA fallback.
- **Monitoring stack.** Application logging follows `docs/logging-sop.md` (JSON to stdout via `core.logging.configure_logging()`, structured fields, request-ID propagation). Log aggregation, dashboards, and alerting are operational concerns owned externally.
