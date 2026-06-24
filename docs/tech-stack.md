# Tech Stack

This document lists every concrete library and runtime choice in the project, with the reasoning behind each. If a library is not listed here, it is not part of the stack — do not introduce new dependencies without justification.

## Runtime

| Item | Version | Rationale |
|------|---------|-----------|
| Python | 3.11+ | Async-friendly, mature typing, broad ML library support |
| PostgreSQL | 16+ | Stable pgvector support, mature ecosystem |
| pgvector | 0.7+ | Native vector type with HNSW / IVFFlat indexes available when needed |

## Package management

| Item | Rationale |
|------|-----------|
| `uv` 0.5+ | Fast resolver, native workspace support for monorepo, replaces pip + virtualenv + pip-tools in one tool |

## Web layer

| Library | Used for | Rationale |
|---------|----------|-----------|
| `fastapi` 0.115+ | HTTP framework | Async-first, Pydantic v2 native, auto-generates OpenAPI |
| `uvicorn[standard]` 0.32+ | ASGI server | Standard pairing with FastAPI |
| `pydantic` 2.x | Validation | Bundled with FastAPI |
| `pydantic-settings` 2.x | Config from .env | Validates env vars at process startup |

## Database layer

| Library | Used for | Rationale |
|---------|----------|-----------|
| `sqlalchemy[asyncio]` 2.0+ | ORM | Type-safe, async support, mature with pgvector |
| `asyncpg` 0.30+ | Postgres driver | Fastest async driver for Postgres |
| `pgvector` 0.3+ (Python pkg) | pgvector type adapter for SQLAlchemy | Maps `Vector` to a SQLAlchemy column type |
| `alembic` 1.13+ | Schema migrations | Standard Python migration tool, autogenerate works well with SQLAlchemy 2.0 |

## ML layer

| Library | Used for | Rationale |
|---------|----------|-----------|
| `sentence-transformers` 3.2+ | Embedding inference | Simplest wrapper over HF for `embeddinggemma-300m` |
| `llama-cpp-python` 0.3+ | LLM inference for cluster labeling | C++ backend (llama.cpp) with SIMD, AVX2, Metal — 3–5× faster than PyTorch CPU for same model/quantization depth |
| `torch` 2.4+ (CPU build on Linux/Windows) | Tensor backend for `sentence-transformers` | Required by sentence-transformers; not used by labeling. Pinned to PyTorch's CPU index in `backend/pyproject.toml` so `nvidia-*` / `cuda-*` / `triton` wheels are never pulled into the image (no deploy target has an NVIDIA GPU). macOS host installs use the standard PyPI wheel (Metal-capable). |
| `umap-learn` 0.5+ | Dimensionality reduction | Best practice before HDBSCAN on high-dim embeddings |
| `hdbscan` 0.8.38+ | Clustering | Algorithm specified by PRD |
| `scikit-learn` 1.5+ | Utility: TF-IDF, vector ops, helpers | Standard ML toolkit for non-DL tasks |

## Active models

| Purpose | Model | Format | Output / Footprint |
|---------|-------|--------|--------------------|
| Embedding | `google/embeddinggemma-300m` | HuggingFace (sentence-transformers) | 768-dim, ~300MB on disk |
| LLM labeling | `bartowski/gemma-2-2b-it-GGUF` — `gemma-2-2b-it-Q4_K_M.gguf` | GGUF Q4_K_M | ~1.6GB on disk, ~2GB RAM |

Switching the embedding model requires a schema migration (vector dimension) and a full re-embed of all articles. See `decisions.md` (D4).

## Ingestion

| Library | Used for | Rationale |
|---------|----------|-----------|
| `feedparser` 6.0+ | RSS parsing | Tolerant of malformed feeds, handles timezone and encoding edge cases |
| `httpx` 0.27+ | HTTP client | Async, supports parallel fetching of all RSS sources |
| `lxml` 5.3+ | XML parsing for sitemaps | Fast, robust |
| `trafilatura` 1.9+ | Article body extraction | Boilerplate removal (nav, ads, footer) from raw HTML; fast path in the two-phase scraper (D25) |
| `playwright` 1.44+ | Headless Chromium fallback scraper | JS-rendered pages that trafilatura+httpx cannot reach; deferred background worker in pipeline-daemon (D25) |
| `google-api-python-client` 2.0+ | Google Search Console API client | Official Google client for Search Analytics API v1 |
| `google-auth` 2.0+ | GSC service account credentials | Handles service account JWT auth for Google APIs |

## AI Analyst

| Library | Used for | Rationale |
|---------|----------|-----------|
| `openai` >=1.40 (currently 2.43.x) | OpenAI-compatible HTTP client for the `analyst` package | Vendor coupling isolated in `analyst/providers.py`; switch vendor via `ANALYST_LLM_PROVIDER` (see `docs/llm-models.md`). Local vs API = base-URL swap, no torch. Lives in the shared `llm` package (provider presets + structured output), reused by analyst and labeling. |

## Operational

| Library | Used for | Rationale |
|---------|----------|-----------|
| `click` 8.1+ | CLI | Decorator-based, simple to expose pipeline steps as commands |
| `python-json-logger` 2.0+ | Structured logging | JSON logs to stdout for downstream aggregation. Configuration and contract: `docs/logging-sop.md` |

Scheduling lives inside the `pipeline-daemon` as plain `asyncio` tasks (D24). There is no host `cron`, no `systemd` timer, and no standalone scheduler library (APScheduler / Celery / Prefect remain explicitly avoided). The daily cluster + label tick is configured via `TIMEZONE`, `CLUSTER_SCHEDULE_HOUR`, `CLUSTER_SCHEDULE_MINUTE` env vars; default is 06:00 WIB.

## Testing & quality

| Tool | Used for |
|------|----------|
| `pytest` 8.3+ | Test framework |
| `pytest-asyncio` 0.24+ | Async test support |
| `ruff` 0.7+ | Linter + formatter (replaces black, isort, flake8) |
| `mypy` 1.13+ | Static type checking — optional but recommended |

## Containerization

| Tool | Used for |
|------|----------|
| Docker | Container runtime |
| docker-compose v2 | Local development orchestration; production composition |

The Dockerfile is multi-stage with two runtime concerns (`api`, `pipeline`), each with build/runtime/dev variants (D24 collapsed the previous `ingest` runtime into `pipeline`). The `api` image excludes torch and transformers — deliberately lean (≤250 MB). The `pipeline` image includes the full ML stack plus ingest deps (≤6 GB). See `architecture.md` for the split rationale and `docs/docker-sop.md` for layer-cache rules, image budgets, healthchecks, and runtime hardening (`USER app`, BuildKit, `.dockerignore`). Operational use of the compose stack — start/stop, exec, alembic, recovery — lives in `docs/operations-sop.md`.

## What was rejected and why

| Rejected | Reason |
|----------|--------|
| Sigma.js / Cytoscape / react-force-graph / vis-network | Full network-graph frameworks with richer APIs than needed for a single force-directed visualization. D3 force simulation covers the use case with less bundle weight. |
| Recharts / Chart.js | General-purpose charting libraries not needed for this product. |
| Ollama for local LLM serving | Adds a separate sidecar service and HTTP overhead for a batch-only, single-consumer workload. |
| `transformers` + `bitsandbytes` for LLM labeling | PyTorch CPU inference for Gemma 2B runs 5–30 s per inference even with bitsandbytes nf4, which has no AVX2 or Metal path. `llama-cpp-python` with GGUF is 3–5× faster on the same hardware. |
| Celery / RabbitMQ / Redis Streams | Pipeline orchestration is a singleton daemon driven by `pg_notify` plus an in-process `asyncio` scheduler (D24). A queue adds infrastructure with no scaling benefit at this load. |
| APScheduler / Prefect / Dagster | Plain `asyncio` scheduling inside the pipeline daemon is sufficient; an external scheduler library adds operational surface without value. |
| Host `cron` / `systemd timer` | Replaced by the daemon-internal scheduler in D24. Keeps timezone handling and supervision in one place. |
| Kubernetes / microservices split | Single VPS, single team, single user persona. Premature distribution. |
| Redis cache layer | Read load is negligible (one user, one morning open). Postgres is sufficient. |
| Qdrant / Milvus / Weaviate / Pinecone | pgvector handles thousands of vectors trivially. A separate vector DB doubles operational surface for no benefit at this scale. |
| HNSW / IVFFlat index | Not required by the happy path (no similarity search queries). Add when a future feature actually needs it. |
| GPU server | embeddinggemma-300m and Gemma 2B 4-bit run acceptably on CPU at our daily batch scale. |
| Multiple parallel embedding models in production | Embeddings from different model spaces are mathematically incomparable. A/B test offline in notebooks. |
| `c-TF-IDF` / top-keyword cluster labels | Quality gap vs LLM is large enough to break the dashboard's UX. LLM compute cost is acceptable. |
| Flat package layout (no `src/`) | src layout forces tested code to be the installed code, catching packaging bugs early. |
| GraphQL | REST is sufficient for the current endpoint surface. |
| WebSockets | Dashboard is poll-based; no real-time push need. |

## Resource footprint

Per-model footprints are listed in §"Active models". Process-level RAM budgets and the VPS minimum are in `docs/operations-sop.md` §Resource budgets.
