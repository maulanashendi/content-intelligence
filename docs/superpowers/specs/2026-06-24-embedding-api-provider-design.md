# Embedding → API provider (SP3) — Design

- **Date:** 2026-06-24
- **Status:** DRAFT — needs spec review (higher-risk than SP1/SP2)
- **Scope owner:** `backend/packages/embedding`, `backend/packages/llm` (new embedding capability), `core/config.py`, `pipeline` (re-embed step), Dockerfile, docs
- **Parent effort:** Full-API / 2 GB VPS — **SP3 of 4**. SP1 (shared `llm`) + SP2 (labeling→API) merged.

## 1. Context & goal

`embedding` loads `embeddinggemma-300m` via `sentence-transformers` + **`torch`** — ~2 GB resident and the single reason `torch` is in the image. Moving embedding to an API removes the last on-box model and gets the pipeline daemon under the 2 GB budget. Unlike SP2, this is **not** a clean swap: the embedding model defines the vector space, so changing it **invalidates all existing vectors** → a full re-embed of all 31k articles is mandatory, and cluster quality (the core product) must be validated before cutover.

### Why this is the risky SP
- **Irreversible-ish data migration:** all `article_embedding` rows are recomputed; old `embeddinggemma` vectors are discarded.
- **Core-product risk:** clustering (UMAP→HDBSCAN) quality depends entirely on embedding quality, especially for Indonesian text. A worse model = worse clusters = worse dashboard.
- **New vendor surface:** the chat side uses OpenRouter, which does **not** serve embeddings. Embeddings need a separate provider (OpenAI or Gemini).

## 2. Decisions & assumptions (documented; veto at spec review)

1. **Keep `vector(768)` — no schema migration.** Use an API model that yields 768 dims: **Gemini `text-embedding-004`** (native 768, multilingual — recommended for Indonesian) **or** OpenAI `text-embedding-3-small` with `dimensions=768`. Model/endpoint are config-driven; the dim==768 guard stays.
2. **Embedding uses a raw base_url, NOT the chat `PRESETS`.** Embedding vendors differ from chat (OpenRouter has no embeddings; Gemini needs its own endpoint), so embedding config takes an explicit `EMBEDDING_API_BASE_URL` rather than reusing chat presets. The client still rides the `openai` SDK's `embeddings.create` against any OpenAI-compatible `/embeddings` endpoint (OpenAI direct; Gemini via its OpenAI-compat base URL).
3. **`EMBEDDING_PROVIDER=local` default** (back-compat). `api` → the new `llm` embedding client; `torch`/`sentence-transformers` are lazy and never imported on the API path.
4. **Re-embed is a gated, explicit operation** — never automatic. A `pipeline.cli reembed` step clears embeddings not matching the target model and re-embeds all (resumable via the existing `~exists` check). Clustering must not run mid-re-embed.
5. **Quality validation precedes cutover** — a non-destructive sample comparison with a human go/no-go gate (see §6). The irreversible production re-embed happens only after sign-off.
6. **One image; `torch` stays installed but lazy.** Image size is acceptable; the RAM win comes from never importing `torch` at runtime in `api` mode.
7. **Cost:** ~$0.6/month + a one-time ~$0.44 re-embed (text-embedding-3-small rates; Gemini similar/cheaper) — negligible.

## 3. Architecture

```
embedding/embedder.py   local: get_embedder() (SentenceTransformer, torch) — lazy, unchanged
embedding/pipeline.py   run(): dispatch local | api per EMBEDDING_PROVIDER
                        api: llm.embeddings.build_embedding_client + .embed(texts, model, dimensions)
llm/embeddings.py       NEW — EmbeddingClient protocol + OpenAICompatibleEmbeddingClient + factory
core/config.py          + EMBEDDING_PROVIDER / EMBEDDING_API_* knobs
pipeline/.../reembed    NEW gated step: clear non-target embeddings → run() to recompute all
```

Storage is unchanged (`article_embedding(article_id unique, model_name, model_version, embedding vector(768))`). `model_name` records the active model, so mixed-model state is detectable; re-embed drives it to a single model.

## 4. The `llm` embedding capability

### 4.1 `llm/embeddings.py` (new, in the shared `llm` package)
```python
from typing import Protocol
from openai import AsyncOpenAI

class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str], *, model: str, dimensions: int | None) -> list[list[float]]: ...

class OpenAICompatibleEmbeddingClient:
    def __init__(self, raw_client: AsyncOpenAI) -> None: self._client = raw_client
    async def embed(self, texts, *, model, dimensions=None):
        kwargs = {"model": model, "input": texts}
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        resp = await self._client.embeddings.create(**kwargs)
        return [d.embedding for d in resp.data]

@lru_cache(...)
def build_embedding_client(api_key, base_url, timeout) -> OpenAICompatibleEmbeddingClient:
    return OpenAICompatibleEmbeddingClient(AsyncOpenAI(base_url=base_url, api_key=api_key or "not-needed", timeout=timeout))
```
Reuses the `openai` dependency already in `llm`. Separate from `providers.py`/chat (different API shape, different vendors). `build_client` (chat) is untouched.

### 4.2 `core/config.py` additions
```
embedding_provider: str = "local"            # local | api
embedding_api_base_url: str = ""             # e.g. https://api.openai.com/v1 or Gemini OpenAI-compat
embedding_api_key: str = ""
embedding_api_model: str = "text-embedding-3-small"
embedding_api_dimensions: int = 768          # must stay 768 (vector(768))
embedding_request_timeout_seconds: float = 60.0
```
(`embedding_model_name`/`_version` stay; on the api path, `model_name` is recorded as `embedding_api_model`.)

### 4.3 `embedding/pipeline.py` dispatch
- `run()` branches: `local` → existing `get_embedder().encode(...)` (unchanged); `api` → batch the same `texts` through `build_embedding_client(...).embed(texts, model=settings.embedding_api_model, dimensions=settings.embedding_api_dimensions)`, then **L2-normalize** (to match the local path's `normalize_embeddings=True`), assert dim==768, and store with `model_name=settings.embedding_api_model`.
- The api path must NOT import `embedding.embedder` / `sentence_transformers` / `torch`.

## 5. Re-embed migration (`pipeline.cli reembed`)

A new gated CLI step (operator-run, never scheduled):
1. In `api` mode, delete `article_embedding` rows whose `model_name != settings.embedding_api_model` (the old `embeddinggemma` rows).
2. Run `embedding.pipeline.run()` — the `~exists` guard means it now embeds every article (all are missing) via the API; resumable if interrupted.
3. Operator then triggers a fresh clustering run (`pipeline.cli cluster`) so clusters are rebuilt in the new vector space.
- Logs counts; idempotent. Clustering is windowed (7 days) so a normal daily run after re-embed is consistent.

## 6. Quality validation gate (pre-cutover, non-destructive)

Before any production re-embed, a helper (`scripts/validate_embeddings.py` or a `pipeline.cli` dry-run) that:
1. Takes a sample (e.g., the current 7-day clustering window, ~7–10k articles).
2. Embeds the sample with the API model into an in-memory/temp set (does NOT touch `article_embedding`).
3. Runs the existing UMAP→HDBSCAN on those vectors.
4. Emits comparison signals vs the current `embeddinggemma` clustering: cluster count, average cluster size, noise ratio, and a sample of top clusters' member titles for **human review**.
- **Human go/no-go.** If Indonesian cluster coherence is comparably good → proceed to §5 cutover. If worse → stop; keep `local`, reconsider model. This task pauses for the operator; it is not auto-passed.

## 7. Testing
- `llm/tests/test_embeddings.py`: `OpenAICompatibleEmbeddingClient.embed` returns vectors from a fake raw client; passes `dimensions` when set, omits when None; `build_embedding_client` caches.
- `embedding/tests`: `run()` dispatch — `local` uses `get_embedder` (mock), `api` uses the embedding client (mock, no torch import); api path normalizes + enforces dim==768; `model_name` recorded as the api model. Config defaults test.
- Re-embed step: unit test the delete-then-embed selection logic against a test DB (mock the client).
- No live API calls in tests.

## 8. Docker & docs
- `api` image: unchanged (already torch-free).
- `pipeline` image: keep `torch`/`sentence-transformers` (local mode); add nothing new at build (the `llm` embedding client uses `openai`, already present via SP2's `labeling → llm`). Confirm `embedding → llm` dep is declared.
- `.env.example`: `EMBEDDING_PROVIDER` block + the api knobs, default `local`, with a Gemini example.
- `docs/llm-models.md`: embedding row notes local|api switch, the 768-dim requirement, the re-embed + validation procedure; `operations-sop.md`: the re-embed runbook.

## 9. Out of scope / deferred
- A torch-free pipeline image variant (one image, lazy import suffices for RAM).
- Auto-scheduled re-embed (always operator-gated).
- SP4 (2 GB compose profile + postgres topology).
- Changing the clustering algorithm or window.

## 10. Open risks
- **Embedding-model quality for Indonesian** is the dominant risk; §6 gate is the mitigation — do not skip it.
- **Re-embed window:** during re-embed, clusters reflect a half-migrated space; run §5 as a single operator session and trigger clustering only after completion.
- **Provider availability/rate limits** for a 31k one-time batch — batch with retries; the `~exists` guard makes it resumable.
