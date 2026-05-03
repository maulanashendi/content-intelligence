# Architecture

This document describes the high-level structure of Editor Intelligence: how modules are organized, how they depend on each other, how data flows through the system, and which processes run when.

## Philosophy

**Modular monorepo, not microservices.** A single git repository contains multiple Python packages that depend on each other through declared interfaces. Each package can be developed, tested, and (when needed) packaged independently, but lives in the same source tree.

**Long-running daemon, not OS cron.** The pipeline orchestrator runs as a singleton daemon. Reactive triggers (`pg_notify`) drive the ingest + embed chain on demand; an in-process scheduler fires the heavier cluster + label run once per day at 06:00 WIB. The product needs are still inherently daily for clustering, but the scheduler now lives in Python — there is no host `cron`, no `systemd` timer, no separate job system. A queue system (Celery, RabbitMQ, Redis Streams) remains rejected: it would add operational surface without delivering value at this scale.

**Single embedding model active at a time.** Switching the embedding model is a deliberate event that requires a schema migration and a full re-embed of all articles. Multi-model serving is not supported.

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

Operational details — compose service names, image targets, command, supervision, recovery — live in `docs/operations-sop.md` §Service map. The daemon must run as a singleton in both dev and prod compose stacks.

The frontend lives in `frontend/` and is built with Bun + Vite. In dev it is part of the same compose stack; production hosting is owned by the deploy team.

## Modules

All backend code lives under `backend/`. The codebase is organized as a `uv` workspace under `backend/packages/`. Each module is an installable Python package with its own `pyproject.toml`.

| Module       | Responsibility                                                                        | Depends on                         |
| ------------ | ------------------------------------------------------------------------------------- | ---------------------------------- |
| `core`       | Shared kernel: SQLAlchemy models, async DB session, Pydantic settings, common types   | (none)                             |
| `ingest`     | Fetch and persist articles from competitor RSS, Tempo sitemap, and Google Trends RSS  | `core`                             |
| `embedding`  | Generate dense vectors for articles using the active embedding model                  | `core`                             |
| `clustering` | Reduce dimensionality (UMAP) and cluster articles (HDBSCAN) into topics               | `core`                             |
| `labeling`   | Generate human-readable cluster labels using a small local LLM                        | `core`                             |
| `scoring`    | Compute trend velocity, novelty, coverage, and the recommendation enum per cluster    | `core`                             |
| `api`        | FastAPI HTTP layer serving the dashboard endpoints and the two write surfaces         | `core`                             |
| `pipeline`   | Long-running daemon that drives reactive ingest + embed and scheduled cluster + label | `core` plus the five batch modules |

The `scoring` module is currently disabled in the daemon's run path: the daemon does not invoke `scoring.pipeline.run` and no new `cluster_insight` rows are written. The package, tables, ORM models, and CLI entry remain in place; existing rows are kept for reference. Re-enabling scoring is a one-line change in the daemon plus a new entry in `decisions.md`.

### Dependency graph

```
ingest ────┐
embedding ─┤
clustering─┼──> core
labeling ──┤
scoring ───┘

pipeline ──> ingest, embedding, clustering, labeling, scoring ──> core
api      ──> core
```

`api` is intentionally lean. It does NOT import any ML module. The API never executes inference; it only reads pre-computed data from the database (and writes to `content_source` and `pipeline_group_lock`). This keeps the API container small (~200MB) and independent of model weights.

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

### Scheduled cluster + label (06:00 WIB daily)

The daemon's internal scheduler emits `pg_notify('pipeline_cluster_label_score_requested')` once per day at 06:00 WIB. The same channel is used by the manual API trigger below — there is exactly one execution path for cluster + label.

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

Label
  - Load LLM singleton (Gemma 2 2B, GGUF Q4_K_M, llama-cpp-python)
  - For each cluster: pick top 3-5 articles by relevance
  - Format prompt with title + first_paragraph
  - Generate label (temperature=0)
  - Update article_cluster.label

Score (currently disabled)
  - The runner skips this step until reinstated. cluster_insight rows
    from earlier runs are retained; new runs do not append.
  │
  ▼
release DB lock
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

The endpoint name keeps `cluster-label-score` for FE compatibility; request body and response shape are unchanged. Inside the daemon, the score step is skipped while scoring is disabled.

### CLI entry points (debugging only)

Each step is also exposed as a standalone CLI command for manual debugging or partial re-runs from inside the container:

```
docker compose --profile manual run --rm pipeline ingest
docker compose --profile manual run --rm pipeline embed
docker compose --profile manual run --rm pipeline cluster
docker compose --profile manual run --rm pipeline label
docker compose --profile manual run --rm pipeline score   # runs but is not part of the daemon path
```

These are operator tools. The supervised daemon is the production execution surface.

## API surface

These endpoints serve the dashboard. Authentication is handled by an upstream gateway (out of scope for this codebase).

| Method   | Path                                   | Purpose                                            |
| -------- | -------------------------------------- | -------------------------------------------------- |
| `GET`    | `/api/v1/clusters/morning`             | Top clusters for Maulana's morning view            |
| `GET`    | `/api/v1/clusters/{cluster_id}`        | Cluster detail with member articles                |
| `GET`    | `/api/v1/clusters/deferred`            | Desk head's deferred-topics view                   |
| `GET`    | `/api/v1/articles`                     | Paginated list of all ingested articles            |
| `GET`    | `/api/v1/sources`                      | List all content sources                           |
| `POST`   | `/api/v1/sources`                      | Add a new RSS source                               |
| `PATCH`  | `/api/v1/sources/{id}`                 | Toggle a source on or off                          |
| `DELETE` | `/api/v1/sources/{id}`                 | Hard delete a source with no articles              |
| `GET`    | `/api/v1/health`                       | DB connectivity check                              |
| `POST`   | `/api/v1/pipeline/cluster-label-score` | Manual trigger: cluster + label (score is skipped) |

All cluster, article, and trend-signal endpoints are read-only. Two write surfaces exist:

- `/api/v1/sources` (POST/PATCH/DELETE) — runtime feed management. POST emits `pg_notify('rss_source_created', <id>)`; the daemon consumes that channel and ingests the new feed within minutes.
- `/api/v1/pipeline/cluster-label-score` (POST) — manual re-cluster. Writes a row to `pipeline_group_lock` and emits `pg_notify('pipeline_cluster_label_score_requested')`. Returns 409 if the lock is held.

The previous `POST /api/v1/pipeline/ingest-embed` is removed. Ingest + embed is fully reactive and needs no operator trigger.

## Data store

A single PostgreSQL 16 instance with the pgvector 0.7+ extension.

- Articles, embeddings, clusters, trend signals, and insights all live in Postgres.
- Vectors are stored in `vector(768)` columns matching the active embedding model.
- No HNSW or IVFFlat index in MVP. The happy path does no similarity search; indexes are added only when a feature requires them.
- HuggingFace and llama-cpp model caches live in `~/.cache/huggingface` and are mounted as a Docker volume in dev to persist across container restarts. The same volume binding is used in prod for the daemon image.
- `pipeline_group_lock` is the single source of truth for "a pipeline group is currently running." The API checks it before issuing `pg_notify`; the daemon writes/deletes rows around runs.

There is no separate vector database, no Redis cache, and no message broker. Adding any of these requires a documented decision in `decisions.md`.

## Runtime: Docker compose, dev to prod

Both environments run via `docker compose` from `backend/`:

- **Dev.** `docker compose up -d` brings up `postgres`, `api`, and `pipeline-daemon`. Source is bind-mounted; reload is live. Frontend is run from `frontend/` with `bun run dev` and points at the compose API. Host `uv run` is reserved for unit tests and IDE integration.
- **Prod.** `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` builds the same images, drops bind mounts, applies `restart: always`, binds the API to `127.0.0.1:8000` (assumes a reverse proxy in front), keeps Postgres off the host network, and rotates `json-file` logs. Required env (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, etc.) is loaded from `backend/.env.prod` (gitignored); the stack refuses to start without it.

The supervised processes are the same in both environments; only the compose overlay differs. Image rebuilds rely on Docker layer cache — dependency layers are stable, so iterating on application code does not invalidate the heavy ML wheel layer. Full operational reference — image targets, healthchecks, recovery procedures — lives in `docs/docker-sop.md` and `docs/operations-sop.md`.

## Out of this codebase

These exist or will exist for the product but are NOT implemented here:

- **Authentication and identity.** Handled by an upstream gateway by another team.
- **Production deployment infrastructure beyond docker compose.** Image build and compose composition are described in `docs/docker-sop.md`; runtime supervision in `docs/operations-sop.md`. Production orchestration beyond compose (Kubernetes, scaling, secret distribution) is owned by the deploy team.
- **Production hosting / serving config.** `bun run build` outputs static assets; the deploy team owns gateway, nginx, cache headers, and SPA fallback.
- **Monitoring stack.** Application logging follows `docs/logging-sop.md` (JSON to stdout via `core.logging.configure_logging()`, structured fields, request-ID propagation). Log aggregation, dashboards, and alerting are operational concerns owned externally.
