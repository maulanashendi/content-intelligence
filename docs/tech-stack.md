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
| `torch` 2.4+ | Tensor backend for `sentence-transformers` | Required by sentence-transformers; not used by labeling |
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

## Operational

| Library | Used for | Rationale |
|---------|----------|-----------|
| `click` 8.1+ | CLI | Decorator-based, simple to expose pipeline steps as commands |
| `python-json-logger` 2.0+ | Structured logging | JSON logs to stdout for downstream aggregation |

Scheduling is done by `cron` or `systemd timer` on the host, not by an in-app scheduler. APScheduler / Celery / Prefect are explicitly avoided. See `decisions.md` (D9).

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
| docker-compose | Local development orchestration |

The Dockerfile is multi-stage. The `api` image excludes torch and transformers — it is deliberately lean (~200MB). The `pipeline` image includes the full ML stack (~5GB). See `architecture.md` for the rationale behind that split.

## What was rejected and why

| Rejected | Reason |
|----------|--------|
| Sigma.js / Cytoscape / react-force-graph / vis-network | Full network-graph frameworks with richer APIs than needed for a single force-directed visualization. D3 force simulation covers the use case with less bundle weight. |
| Recharts / Chart.js | General-purpose charting libraries not needed for this product. |
| Ollama for local LLM serving | Adds a separate sidecar service and HTTP overhead for a batch-only, single-consumer workload. |
| `transformers` + `bitsandbytes` for LLM labeling | PyTorch CPU inference for Gemma 2B runs 5–30 s per inference even with bitsandbytes nf4, which has no AVX2 or Metal path. `llama-cpp-python` with GGUF is 3–5× faster on the same hardware. |
| Celery / RabbitMQ / Redis Streams | One daily batch job. A queue adds infrastructure with no scaling benefit at this load. |
| APScheduler / Prefect / Dagster | OS-level cron is sufficient for a single daily job. |
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

## Resource footprint estimate

For a VPS hosting both `api` and `pipeline` plus Postgres in development:

| Item | Approximate footprint |
|------|----------------------|
| Postgres working set | ~2GB |
| Embedding model loaded | ~300MB |
| LLM (Gemma 2B Q4_K_M GGUF) loaded | ~2GB |
| UMAP + HDBSCAN peak (during clustering) | ~1GB |
| Python processes overhead | ~500MB each |
| **Suggested minimum** | **8GB RAM, 4 vCPU, 50GB disk** |
