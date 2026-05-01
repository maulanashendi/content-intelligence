# Architecture

This document describes the high-level structure of Editor Intelligence: how modules are organized, how they depend on each other, how data flows through the system, and which processes run when.

## Philosophy

**Modular monorepo, not microservices.** A single git repository contains multiple Python packages that depend on each other through declared interfaces. Each package can be developed, tested, and (when needed) packaged independently, but lives in the same source tree.

**Cron-driven batch pipeline, not event-driven streaming.** The product needs are inherently daily. A queue system would add operational complexity without delivering value at this scale.

**Single embedding model active at a time.** Switching the embedding model is a deliberate event that requires a schema migration and a full re-embed of all articles. Multi-model serving is not supported.

**Read-dominant API with one narrow write surface.** Per `decisions.md` D19, the API exposes `POST/PATCH/DELETE` on `/api/v1/sources` so editors can manage RSS feeds at runtime. Every other table — articles, clusters, embeddings, scoring, GSC metrics, trend signals — is read-only. User actions on cluster/article rows (claim, dismiss, etc.) remain out of scope per PRD Section 6.

## Process topology

Three long-running concerns, plus the database:

| Process               | Lifecycle                  | Trigger                                                   |
| --------------------- | -------------------------- | --------------------------------------------------------- |
| `api`                 | Always running             | HTTP requests from the frontend                           |
| `pipeline`            | Batch run, exits when done | Cron at 06:00 WIB daily                                   |
| `ingest serve` (D20)  | Always running, singleton  | `pg_notify('rss_source_created')` + safety-net poll loop  |
| `postgres`            | Always running             | Hosts pgvector data                                       |

The `ingest serve` daemon picks up sources added through `POST /api/v1/sources` (D19) and runs a periodic `_run_once` poll as a fallback when notifications are missed. It must be deployed as a singleton — its blocked-source map and immediate queue are process-local.

The frontend is served separately and is owned by another team.

## Modules

All backend code lives under `backend/`. The codebase is organized as a `uv` workspace under `backend/packages/`. Each module is an installable Python package with its own `pyproject.toml`.

| Module       | Responsibility                                                                       | Depends on                         |
| ------------ | ------------------------------------------------------------------------------------ | ---------------------------------- |
| `core`       | Shared kernel: SQLAlchemy models, async DB session, Pydantic settings, common types  | (none)                             |
| `ingest`     | Fetch and persist articles from competitor RSS, Tempo sitemap, and Google Trends RSS | `core`                             |
| `embedding`  | Generate dense vectors for articles using the active embedding model                 | `core`                             |
| `clustering` | Reduce dimensionality (UMAP) and cluster articles (HDBSCAN) into topics              | `core`                             |
| `labeling`   | Generate human-readable cluster labels using a small local LLM                       | `core`                             |
| `scoring`    | Compute trend velocity, novelty, coverage, and the recommendation enum per cluster   | `core`                             |
| `api`        | FastAPI HTTP layer serving the dashboard's three endpoints                           | `core`                             |
| `pipeline`   | Orchestrator that invokes the five batch modules in order via the daily cron         | `core` plus the five batch modules |

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

`api` is intentionally lean. It does NOT import any ML module. The API never executes inference; it only reads pre-computed data from the database. This keeps the API container small (~200MB) and independent of model weights.

Batch modules do not import each other. Shared logic between them lives in `core`. This rule prevents accidental coupling and keeps each module testable in isolation.

## Daily pipeline flow

Cron triggers `python -m pipeline.cli run-daily` at 06:00 WIB. The orchestrator runs five steps sequentially:

```
06:00  Ingest
       - Fetch ~10 RSS sources in parallel (httpx + feedparser)
       - Parse Tempo internal sitemap
       - Parse Google Trends RSS feeds
       - Upsert articles (ON CONFLICT url DO NOTHING)
       - Upsert trend_signal rows + trend_signal_article join rows
       - Update content_source.status (active / error)

       Embed
       - Query articles WHERE NOT EXISTS embedding
       - Load embedder singleton (google/embeddinggemma-300m, 768 dim)
       - Encode in batches of 32-64
       - Insert article_embedding rows

       Cluster
       - Load embeddings from the last 30 days
       - UMAP reduce 768 -> 30 dimensions (random_state=42 for stability)
       - HDBSCAN cluster
       - Mark all previous article_cluster.is_current = false
       - Insert new cluster_run, article_cluster, article_cluster_member rows

       Label
       - Load LLM singleton (Gemma 2B 4-bit quantized)
       - For each cluster: pick top 3-5 articles by relevance_score
       - Format prompt with title + first_paragraph
       - Generate label (temperature=0)
       - Update article_cluster.label

       Score
       - Per cluster: compute trend_velocity, novelty_score, coverage_score
       - Derive recommendation enum from thresholds
       - Insert cluster_insight rows

08:00  Pipeline complete (target). Dashboard ready before 09:00.
```

Each step is also exposed as a standalone CLI command for manual debugging or partial re-runs:

```
python -m pipeline.cli ingest
python -m pipeline.cli embed
python -m pipeline.cli cluster
python -m pipeline.cli label
python -m pipeline.cli score
```

## API surface

Three endpoints serve the dashboard's happy path. Authentication is handled by an upstream gateway (out of scope for this codebase).

| Method | Path                            | Purpose                                    |
| ------ | ------------------------------- | ------------------------------------------ |
| `GET`  | `/api/v1/clusters/morning`      | Top 10 clusters for Maulana's morning view |
| `GET`  | `/api/v1/clusters/{cluster_id}` | Cluster detail with member articles        |
| `GET`  | `/api/v1/clusters/deferred`     | Desk head's deferred-topics view           |
| `GET`  | `/api/v1/health`                | DB connectivity check                      |

All cluster, article, and trend-signal endpoints are read-only. The `/api/v1/sources` endpoints are the only write surface (POST/PATCH/DELETE) — see `decisions.md` D19. POST triggers `pg_notify('rss_source_created', <id>)`; the running `serve` daemon (D20) consumes that channel and ingests the new feed within minutes, while the daily cron pipeline keeps running its full ingest+embed+cluster+label+score chain.

## Data store

A single PostgreSQL 16 instance with the pgvector 0.7+ extension.

- Articles, embeddings, clusters, trend signals, and insights all live in Postgres.
- Vectors are stored in `vector(768)` columns matching the active embedding model.
- No HNSW or IVFFlat index in MVP. The happy path does no similarity search; indexes are added only when a feature requires them.
- HuggingFace model cache lives in `~/.cache/huggingface` and is mounted as a Docker volume in development to persist across container restarts.

There is no separate vector database, no Redis cache, and no message broker. Adding any of these requires a documented decision in `decisions.md`.

## Out of this codebase

These exist or will exist for the product but are NOT implemented here:

- **Authentication and identity.** Handled by an upstream gateway by another team.
- **Production deployment infrastructure.** The Dockerfile and docker-compose.yml in this repo are for local development. Production orchestration is owned by the deploy team.
- **Frontend.** Lives in `template-fe/`. The only contract is the JSON shape of the four API endpoints.
- **Monitoring stack.** The application emits structured JSON logs to stdout. Log aggregation, dashboards, and alerting are operational concerns owned externally.
