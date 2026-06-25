# Embedding → API Provider (SP3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `EMBEDDING_PROVIDER=local|api` switch so article embedding can run via OpenRouter's `/embeddings` endpoint (`openai/text-embedding-3-large` @ 768 dims) instead of on-box `torch`, removing the last model from RAM, while keeping `vector(768)` unchanged.

**Architecture:** A new embedding capability in the shared `llm` package (separate from chat `providers.py`). `embedding/pipeline.run()` dispatches on `settings.embedding_provider`: `local` keeps the lazy `sentence-transformers` path untouched; `api` calls the OpenRouter embeddings client and L2-normalizes the result. A gated, operator-only `pipeline.cli reembed` step migrates the existing 31k articles, preceded by a non-destructive quality-validation script (human go/no-go).

**Tech Stack:** Python 3.11, uv workspace, `openai` SDK (`AsyncOpenAI.embeddings.create`), pydantic-settings, numpy, SQLAlchemy async, click, pytest (asyncio_mode=auto), UMAP+HDBSCAN (validation only).

## Global Constraints

- `vector(768)` is fixed — **no schema migration**. The `dim == 768` guard stays. API model truncates to 768 via the `dimensions` param.
- `api` (FastAPI) package must never import ML/torch. This plan only touches `embedding`, `llm`, `core`, `pipeline`, `clustering` (a pure helper) — never `api`.
- The `api`-mode embedding path must NOT import `embedding.embedder` / `sentence_transformers` / `torch`. Heavy imports stay lazy, inside the `local` branch only.
- Chosen model: `openai/text-embedding-3-large`, `dimensions=768`, via OpenRouter (`https://openrouter.ai/api/v1`), reusing the existing OpenRouter API key.
- Cross-module imports must be declared in `pyproject.toml` (so `embedding → llm` must be added).
- Re-embed is operator-gated, **never** scheduled — it must NOT be added to `_STEP_RUNNERS` (which `run-daily` iterates).
- All logs JSON to stdout via `core.logging`; no `print()`.
- No comments explaining WHAT; only non-obvious WHY.
- Tests run from `backend/`: `./.venv/bin/python -m pytest packages/<module>/tests/`. DB-backed suites need `docker compose up -d postgres` first. Never combine unrelated package suites in one pytest invocation (ImportPathMismatchError) — run each package's tests separately.

---

### Task 1: `llm` embedding client

**Files:**
- Create: `backend/packages/llm/src/llm/embeddings.py`
- Test: `backend/packages/llm/tests/test_embeddings.py`

**Interfaces:**
- Consumes: `openai.AsyncOpenAI` (already a dependency of `llm`).
- Produces:
  - `class EmbeddingClient(Protocol)` with `async def embed(self, texts: list[str], *, model: str, dimensions: int | None = None) -> list[list[float]]`
  - `class OpenAICompatibleEmbeddingClient` (constructor takes a raw `AsyncOpenAI`)
  - `def build_embedding_client(api_key: str, base_url: str, timeout: float, headers: tuple[tuple[str, str], ...] = ()) -> OpenAICompatibleEmbeddingClient` (lru_cached)

This is a leaf module in the existing `llm` package; no DB. `llm/tests/conftest.py` already disables the DB fixtures.

- [ ] **Step 1: Write the failing test**

Create `backend/packages/llm/tests/test_embeddings.py`:

```python
from unittest.mock import AsyncMock, MagicMock

from llm.embeddings import OpenAICompatibleEmbeddingClient, build_embedding_client


def _make_raw_client(vectors: list[list[float]]) -> MagicMock:
    raw = MagicMock()
    response = MagicMock()
    response.data = [MagicMock(embedding=v) for v in vectors]
    raw.embeddings.create = AsyncMock(return_value=response)
    return raw


async def test_embed_returns_vectors_in_order():
    raw = _make_raw_client([[0.1, 0.2], [0.3, 0.4]])
    client = OpenAICompatibleEmbeddingClient(raw)
    out = await client.embed(["a", "b"], model="m", dimensions=768)
    assert out == [[0.1, 0.2], [0.3, 0.4]]


async def test_embed_passes_dimensions_when_set():
    raw = _make_raw_client([[0.0]])
    client = OpenAICompatibleEmbeddingClient(raw)
    await client.embed(["a"], model="m", dimensions=768)
    _, kwargs = raw.embeddings.create.call_args
    assert kwargs["dimensions"] == 768
    assert kwargs["model"] == "m"
    assert kwargs["input"] == ["a"]


async def test_embed_omits_dimensions_when_none():
    raw = _make_raw_client([[0.0]])
    client = OpenAICompatibleEmbeddingClient(raw)
    await client.embed(["a"], model="m", dimensions=None)
    _, kwargs = raw.embeddings.create.call_args
    assert "dimensions" not in kwargs


def test_build_embedding_client_caches():
    a = build_embedding_client("k", "https://openrouter.ai/api/v1", 60.0)
    b = build_embedding_client("k", "https://openrouter.ai/api/v1", 60.0)
    assert a is b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest packages/llm/tests/test_embeddings.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm.embeddings'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/packages/llm/src/llm/embeddings.py`:

```python
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI


class EmbeddingClient(Protocol):
    async def embed(
        self, texts: list[str], *, model: str, dimensions: int | None = None
    ) -> list[list[float]]: ...


class OpenAICompatibleEmbeddingClient:
    def __init__(self, raw_client: AsyncOpenAI) -> None:
        self._client = raw_client

    async def embed(
        self, texts: list[str], *, model: str, dimensions: int | None = None
    ) -> list[list[float]]:
        kwargs: dict = {"model": model, "input": texts}
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        response = await self._client.embeddings.create(**kwargs)
        return [item.embedding for item in response.data]


@lru_cache(maxsize=4)
def build_embedding_client(
    api_key: str,
    base_url: str,
    timeout: float,
    headers: tuple[tuple[str, str], ...] = (),
) -> OpenAICompatibleEmbeddingClient:
    raw = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key or "not-needed",
        timeout=timeout,
        # openai SDK treats an empty dict the same as no headers; None is the correct sentinel
        default_headers=dict(headers) or None,
    )
    return OpenAICompatibleEmbeddingClient(raw)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest packages/llm/tests/test_embeddings.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Lint**

Run: `./.venv/bin/python -m ruff check packages/llm/src/llm/embeddings.py packages/llm/tests/test_embeddings.py`
Expected: no errors (imports at top of file).

- [ ] **Step 6: Commit**

```bash
git add packages/llm/src/llm/embeddings.py packages/llm/tests/test_embeddings.py
git commit -m "feat(llm): add OpenAI-compatible embedding client (SP3)"
```

---

### Task 2: Config knobs + `api`/`local` dispatch in `embedding/pipeline.py`

**Files:**
- Modify: `backend/packages/embedding/pyproject.toml` (add `llm` + `numpy` deps)
- Modify: `backend/packages/core/src/core/config.py` (add `embedding_*` knobs after the labeling block)
- Modify: `backend/packages/embedding/src/embedding/pipeline.py` (dispatch)
- Modify: `backend/packages/embedding/tests/test_embed_pipeline.py` (fix pre-existing red test + add api-path test)

**Interfaces:**
- Consumes: `llm.embeddings.build_embedding_client`, `llm.providers.attribution_headers`, `core.config.settings`.
- Produces (used by Task 3):
  - `async def run() -> int` (unchanged signature; now provider-aware)
  - `def _active_model_name() -> str` — returns `settings.embedding_api_model` when `embedding_provider == "api"`, else `settings.embedding_model_name`
  - `async def _encode(texts: list[str]) -> np.ndarray` (internal)

NOTE: the existing test `test_run_embeds_unembedded_articles` is **already failing** on `master` (its `fake_encode` mock rejects the `show_progress_bar` kwarg). This task fixes it.

- [ ] **Step 1: Declare the `embedding → llm` dependency**

Edit `backend/packages/embedding/pyproject.toml`. Change the `dependencies` and `[tool.uv.sources]` blocks to:

```toml
dependencies = [
  "core",
  "llm",
  "sentence-transformers>=3.2",
  "torch>=2.4",
  "numpy>=1.26",
  "click>=8.1",
]

[tool.uv.sources]
core = { workspace = true }
llm = { workspace = true }
```

- [ ] **Step 2: Sync the workspace**

Run: `uv lock && uv sync --all-packages`
Expected: lock updates `embedding`'s deps; venv keeps pytest + all members (do NOT use `uv sync --package embedding` — it prunes the host venv).
Verify: `./.venv/bin/python -c "import llm.embeddings, embedding.pipeline"` prints nothing (no error).

- [ ] **Step 3: Add config knobs**

In `backend/packages/core/src/core/config.py`, immediately after the labeling block (after `labeling_attribution_title: str = ""`), add:

```python
    # Embedding backend (SP3): "local" = embeddinggemma (torch); "api" = OpenRouter embeddings.
    embedding_provider: str = "local"
    embedding_api_base_url: str = "https://openrouter.ai/api/v1"
    embedding_api_key: str = ""
    embedding_api_model: str = "openai/text-embedding-3-large"
    embedding_api_dimensions: int = 768
    embedding_request_timeout_seconds: float = 60.0
    embedding_attribution_referer: str = ""
    embedding_attribution_title: str = ""
```

- [ ] **Step 4: Write the failing api-path test and fix the red local test**

Replace the entire contents of `backend/packages/embedding/tests/test_embed_pipeline.py` with:

```python
import uuid
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from core.config import settings
from core.models import Article, ArticleEmbedding, ContentSource, SourceType
from embedding.pipeline import run
from sqlalchemy import select


async def _seed_source(session):
    source = ContentSource(
        name="test-src",
        url=f"http://example-{uuid.uuid4()}.com",
        source_type=SourceType.rss,
    )
    session.add(source)
    await session.flush()
    return source


async def _seed_article(session, source_id):
    article = Article(
        source_id=source_id,
        title="Economy headline",
        url=f"http://example-{uuid.uuid4()}.com/article",
    )
    session.add(article)
    await session.flush()
    return article


def _make_embedder():
    mock = MagicMock()

    def fake_encode(texts, **kwargs):
        return np.zeros((len(texts), 768), dtype=np.float32)

    mock.encode.side_effect = fake_encode
    return mock


@asynccontextmanager
async def _session_cm(db_session):
    yield db_session


@pytest.mark.asyncio
async def test_run_embeds_unembedded_articles_local(db_session):
    source = await _seed_source(db_session)
    article = await _seed_article(db_session, source.id)

    with (
        patch("embedding.embedder.get_embedder", return_value=_make_embedder()),
        patch("embedding.pipeline.get_session", lambda: _session_cm(db_session)),
    ):
        count = await run()

    assert count == 1
    rows = (
        (await db_session.execute(
            select(ArticleEmbedding).where(ArticleEmbedding.article_id == article.id)
        )).scalars().all()
    )
    assert len(rows) == 1
    assert rows[0].model_name == "google/embeddinggemma-300m"


@pytest.mark.asyncio
async def test_run_is_noop_when_all_embedded_local(db_session):
    source = await _seed_source(db_session)
    article = await _seed_article(db_session, source.id)
    db_session.add(
        ArticleEmbedding(
            article_id=article.id,
            model_name="google/embeddinggemma-300m",
            embedding=[0.0] * 768,
        )
    )
    await db_session.flush()

    mock_embedder = _make_embedder()
    with (
        patch("embedding.embedder.get_embedder", return_value=mock_embedder),
        patch("embedding.pipeline.get_session", lambda: _session_cm(db_session)),
    ):
        count = await run()

    assert count == 0
    mock_embedder.encode.assert_not_called()


@pytest.mark.asyncio
async def test_run_api_path_uses_embedding_client_and_normalizes(db_session, monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "api")
    monkeypatch.setattr(settings, "embedding_api_model", "openai/text-embedding-3-large")
    source = await _seed_source(db_session)
    article = await _seed_article(db_session, source.id)

    mock_client = MagicMock()

    async def fake_embed(texts, *, model, dimensions):
        assert model == "openai/text-embedding-3-large"
        assert dimensions == 768
        # un-normalized vector [3, 4, 0...]: norm 5 -> expect [0.6, 0.8, 0...]
        return [[3.0, 4.0] + [0.0] * 766 for _ in texts]

    mock_client.embed = fake_embed
    get_embedder_spy = MagicMock()

    with (
        patch("llm.embeddings.build_embedding_client", return_value=mock_client),
        patch("embedding.embedder.get_embedder", get_embedder_spy),
        patch("embedding.pipeline.get_session", lambda: _session_cm(db_session)),
    ):
        count = await run()

    assert count == 1
    get_embedder_spy.assert_not_called()  # api path must not touch the local embedder
    rows = (
        (await db_session.execute(
            select(ArticleEmbedding).where(ArticleEmbedding.article_id == article.id)
        )).scalars().all()
    )
    assert rows[0].model_name == "openai/text-embedding-3-large"
    assert abs(rows[0].embedding[0] - 0.6) < 1e-6
    assert abs(rows[0].embedding[1] - 0.8) < 1e-6
```

- [ ] **Step 5: Run tests to verify the api test fails (and confirm baseline)**

Run: `docker compose up -d postgres && ./.venv/bin/python -m pytest packages/embedding/tests/test_embed_pipeline.py -q`
Expected: `test_run_api_path_...` FAILS (current `run()` has no api branch and ignores `embedding_provider`). The two local tests may pass or fail depending on the dispatch not yet existing — both are fixed by Step 6.

- [ ] **Step 6: Implement the dispatch**

Replace the entire contents of `backend/packages/embedding/src/embedding/pipeline.py` with:

```python
import asyncio
import logging

import numpy as np
from core.config import settings
from core.db import get_session
from core.models import Article, ArticleEmbedding
from sqlalchemy import exists, select

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _active_model_name() -> str:
    if settings.embedding_provider == "api":
        return settings.embedding_api_model
    return settings.embedding_model_name


def _encode_local(texts: list[str]) -> np.ndarray:
    from embedding.embedder import get_embedder

    embedder = get_embedder()
    return embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)


async def _encode_api(texts: list[str]) -> np.ndarray:
    from llm.embeddings import build_embedding_client
    from llm.providers import attribution_headers

    client = build_embedding_client(
        settings.embedding_api_key,
        settings.embedding_api_base_url,
        settings.embedding_request_timeout_seconds,
        attribution_headers(
            settings.embedding_attribution_referer,
            settings.embedding_attribution_title,
        ),
    )
    raw = await client.embed(
        texts,
        model=settings.embedding_api_model,
        dimensions=settings.embedding_api_dimensions,
    )
    return _l2_normalize(np.asarray(raw, dtype=np.float32))


async def _encode(texts: list[str]) -> np.ndarray:
    if settings.embedding_provider == "api":
        return await _encode_api(texts)
    return await asyncio.to_thread(_encode_local, texts)


async def run() -> int:
    model_name = _active_model_name()
    total = 0

    async with get_session() as session:
        while True:
            subq = select(ArticleEmbedding.article_id).where(
                ArticleEmbedding.article_id == Article.id
            )
            result = await session.execute(
                select(Article.id, Article.title, Article.first_paragraph, Article.content)
                .where(~exists(subq))
                .limit(BATCH_SIZE)
            )
            rows = result.all()
            if not rows:
                break

            texts = [
                f"{title}\n{body}" if (body := (content or first_paragraph)) else title
                for _, title, first_paragraph, content in rows
            ]
            vectors = await _encode(texts)
            if vectors.shape[1] != 768:
                raise ValueError(f"embedding dim mismatch: got {vectors.shape[1]}, expected 768")

            for (article_id, _, _, _), vector in zip(rows, vectors, strict=True):
                session.add(
                    ArticleEmbedding(
                        article_id=article_id,
                        model_name=model_name,
                        model_version=settings.embedding_model_version or None,
                        embedding=vector.tolist(),
                    )
                )

            await session.commit()
            total += len(rows)
            logger.info("embedded batch", extra={"count": len(rows), "total": total})

    return total
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest packages/embedding/tests/test_embed_pipeline.py -q`
Expected: PASS (3 passed) — both local tests and the api test green.

- [ ] **Step 8: Lint**

Run: `./.venv/bin/python -m ruff check packages/embedding packages/core/src/core/config.py`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add packages/embedding/pyproject.toml packages/core/src/core/config.py \
        packages/embedding/src/embedding/pipeline.py \
        packages/embedding/tests/test_embed_pipeline.py uv.lock
git commit -m "feat(embedding): EMBEDDING_PROVIDER local|api dispatch via llm client (SP3)"
```

---

### Task 3: Gated `reembed` migration step

**Files:**
- Modify: `backend/packages/embedding/src/embedding/pipeline.py` (add `reembed()`)
- Modify: `backend/packages/embedding/tests/test_embed_pipeline.py` (add reembed test)
- Modify: `backend/packages/pipeline/src/pipeline/cli.py` (add gated `reembed` command — NOT in `_STEP_RUNNERS`)
- Create: `backend/packages/pipeline/tests/test_reembed_cli.py`

**Interfaces:**
- Consumes: `embedding.pipeline.run`, `embedding.pipeline._active_model_name`, `core.db.get_session`, `core.models.ArticleEmbedding`.
- Produces: `async def reembed() -> dict[str, int]` returning `{"deleted": int, "embedded": int}`.

- [ ] **Step 1: Write the failing reembed test**

Append to `backend/packages/embedding/tests/test_embed_pipeline.py`:

```python
async def test_reembed_clears_non_target_then_recomputes(db_session, monkeypatch):
    from embedding.pipeline import reembed

    monkeypatch.setattr(settings, "embedding_provider", "api")
    monkeypatch.setattr(settings, "embedding_api_model", "openai/text-embedding-3-large")
    source = await _seed_source(db_session)
    stale = await _seed_article(db_session, source.id)
    keep = await _seed_article(db_session, source.id)
    db_session.add_all(
        [
            ArticleEmbedding(
                article_id=stale.id,
                model_name="google/embeddinggemma-300m",
                embedding=[0.0] * 768,
            ),
            ArticleEmbedding(
                article_id=keep.id,
                model_name="openai/text-embedding-3-large",
                embedding=[0.0] * 768,
            ),
        ]
    )
    await db_session.flush()

    mock_client = MagicMock()

    async def fake_embed(texts, *, model, dimensions):
        return [[1.0] + [0.0] * 767 for _ in texts]

    mock_client.embed = fake_embed

    with (
        patch("llm.embeddings.build_embedding_client", return_value=mock_client),
        patch("embedding.pipeline.get_session", lambda: _session_cm(db_session)),
    ):
        result = await reembed()

    assert result["deleted"] == 1
    assert result["embedded"] == 1  # only the stale article re-embedded; keep was skipped
    rows = (await db_session.execute(select(ArticleEmbedding))).scalars().all()
    assert len(rows) == 2
    assert {r.model_name for r in rows} == {"openai/text-embedding-3-large"}
```

This test is decorated by `asyncio_mode=auto`; no marker needed because the file already imports pytest and the prior tests use `@pytest.mark.asyncio` — add `@pytest.mark.asyncio` above this function to match the file's style.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest packages/embedding/tests/test_embed_pipeline.py::test_reembed_clears_non_target_then_recomputes -q`
Expected: FAIL — `ImportError: cannot import name 'reembed'`.

- [ ] **Step 3: Implement `reembed()`**

In `backend/packages/embedding/src/embedding/pipeline.py`, add `delete` to the sqlalchemy import and append the function at end of file:

Change the import line:
```python
from sqlalchemy import delete, exists, select
```

Append:
```python
async def reembed() -> dict[str, int]:
    """Operator-gated migration: drop embeddings not from the active model, then
    re-embed every now-unembedded article via run(). Resumable (run()'s ~exists
    guard skips already-migrated rows)."""
    model_name = _active_model_name()
    async with get_session() as session:
        result = await session.execute(
            delete(ArticleEmbedding).where(ArticleEmbedding.model_name != model_name)
        )
        await session.commit()
        deleted = result.rowcount or 0
    logger.info("reembed cleared stale embeddings", extra={"deleted": deleted, "model": model_name})
    embedded = await run()
    return {"deleted": deleted, "embedded": embedded}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest packages/embedding/tests/test_embed_pipeline.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Write the failing CLI registration test**

Create `backend/packages/pipeline/tests/test_reembed_cli.py`:

```python
from pipeline.cli import _STEP_RUNNERS, cli


def test_reembed_command_registered():
    assert "reembed" in cli.commands


def test_reembed_not_in_daily_runners():
    # run-daily iterates _STEP_RUNNERS; reembed must never auto-run
    assert "reembed" not in _STEP_RUNNERS
```

- [ ] **Step 6: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest packages/pipeline/tests/test_reembed_cli.py -q`
Expected: `test_reembed_command_registered` FAILS (no such command yet); `test_reembed_not_in_daily_runners` passes.

- [ ] **Step 7: Add the gated CLI command**

In `backend/packages/pipeline/src/pipeline/cli.py`, after the `cluster_label_score_cmd` definition (before `serve`), add:

```python
@cli.command("reembed")
def reembed_cmd() -> None:
    _configure()
    from embedding.pipeline import reembed

    async def _run_locked() -> None:
        try:
            async with hold_lock(GROUP_CLUSTER_LABEL_SCORE):
                result = await reembed()
                logger.info("reembed complete", extra={"counts": result})
        except LockHeld as exc:
            logger.error("reembed blocked: %s", exc)
            sys.exit(1)

    asyncio.run(_run_locked())
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest packages/pipeline/tests/test_reembed_cli.py -q`
Expected: PASS (2 passed).

- [ ] **Step 9: Lint**

Run: `./.venv/bin/python -m ruff check packages/embedding/src/embedding/pipeline.py packages/pipeline/src/pipeline/cli.py packages/pipeline/tests/test_reembed_cli.py`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add packages/embedding/src/embedding/pipeline.py \
        packages/embedding/tests/test_embed_pipeline.py \
        packages/pipeline/src/pipeline/cli.py \
        packages/pipeline/tests/test_reembed_cli.py
git commit -m "feat(pipeline): gated reembed migration step (SP3)"
```

---

### Task 4: Quality-validation gate (clustering helper + operator script)

**Files:**
- Create: `backend/packages/clustering/src/clustering/quality.py`
- Test: `backend/packages/clustering/tests/test_quality.py`
- Create: `backend/scripts/validate_embeddings.py` (operator tool — not unit-tested; no live API in CI)

**Interfaces:**
- Produces: `def cluster_quality_signals(labels) -> dict[str, float]` (keys: `n_articles`, `n_clusters`, `noise_ratio`, `avg_cluster_size`, `largest_cluster_size`).
- The script consumes `clustering.reducer.reduce`, `clustering.clusterer.cluster`, `clustering.quality.cluster_quality_signals`, `llm.embeddings.build_embedding_client`.

- [ ] **Step 1: Write the failing helper test**

Create `backend/packages/clustering/tests/test_quality.py`:

```python
import numpy as np

from clustering.quality import cluster_quality_signals


def test_signals_basic():
    labels = np.array([0, 0, 1, 1, 1, -1, -1])
    s = cluster_quality_signals(labels)
    assert s["n_articles"] == 7
    assert s["n_clusters"] == 2
    assert abs(s["noise_ratio"] - 2 / 7) < 1e-9
    assert abs(s["avg_cluster_size"] - 2.5) < 1e-9
    assert s["largest_cluster_size"] == 3


def test_signals_all_noise():
    labels = np.array([-1, -1, -1])
    s = cluster_quality_signals(labels)
    assert s["n_clusters"] == 0
    assert s["noise_ratio"] == 1.0
    assert s["avg_cluster_size"] == 0.0
    assert s["largest_cluster_size"] == 0


def test_signals_empty():
    s = cluster_quality_signals(np.array([], dtype=int))
    assert s["n_articles"] == 0
    assert s["noise_ratio"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest packages/clustering/tests/test_quality.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'clustering.quality'`.

- [ ] **Step 3: Implement the helper**

Create `backend/packages/clustering/src/clustering/quality.py`:

```python
import numpy as np


def cluster_quality_signals(labels) -> dict[str, float]:
    labels = np.asarray(labels)
    total = int(labels.shape[0])
    if total == 0:
        return {
            "n_articles": 0,
            "n_clusters": 0,
            "noise_ratio": 0.0,
            "avg_cluster_size": 0.0,
            "largest_cluster_size": 0,
        }
    noise = int((labels == -1).sum())
    cluster_ids = sorted(set(labels.tolist()) - {-1})
    sizes = [int((labels == cid).sum()) for cid in cluster_ids]
    return {
        "n_articles": total,
        "n_clusters": len(cluster_ids),
        "noise_ratio": noise / total,
        "avg_cluster_size": (sum(sizes) / len(sizes)) if sizes else 0.0,
        "largest_cluster_size": max(sizes) if sizes else 0,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest packages/clustering/tests/test_quality.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Write the operator validation script**

Create `backend/scripts/validate_embeddings.py`:

```python
"""SP3 pre-cutover embedding quality gate. NON-DESTRUCTIVE: never writes article_embedding.

Embeds the live (already-embedded) article set with each candidate API model,
runs the production UMAP->HDBSCAN, and logs cluster-quality signals + sample
cluster titles for a human go/no-go before the irreversible reembed.

Run (host venv, EMBEDDING_API_KEY set in backend/.env):
    cd backend && ./.venv/bin/python scripts/validate_embeddings.py
"""
import asyncio
import logging

import numpy as np
from clustering.clusterer import cluster as hdbscan_cluster
from clustering.quality import cluster_quality_signals
from clustering.reducer import reduce as umap_reduce
from core.config import settings
from core.db import get_session
from core.logging import configure_logging
from core.models import Article, ArticleEmbedding
from llm.embeddings import build_embedding_client
from sqlalchemy import select

logger = logging.getLogger(__name__)

CANDIDATES = ["openai/text-embedding-3-large", "google/gemini-embedding-001"]
SAMPLE_LIMIT = 8000
EMBED_BATCH = 256


async def _load_sample() -> tuple[list[str], list[str]]:
    async with get_session() as session:
        result = await session.execute(
            select(Article.title, Article.first_paragraph, Article.content)
            .join(ArticleEmbedding, ArticleEmbedding.article_id == Article.id)
            .limit(SAMPLE_LIMIT)
        )
        rows = result.all()
    titles = [title for title, _, _ in rows]
    texts = [
        f"{title}\n{body}" if (body := (content or first_paragraph)) else title
        for title, first_paragraph, content in rows
    ]
    return titles, texts


async def _embed_all(model: str, texts: list[str]) -> np.ndarray:
    client = build_embedding_client(
        settings.embedding_api_key,
        settings.embedding_api_base_url,
        settings.embedding_request_timeout_seconds,
    )
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        out.extend(await client.embed(texts[i : i + EMBED_BATCH], model=model, dimensions=768))
    vectors = np.asarray(out, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


async def main() -> None:
    configure_logging(settings.log_level)
    titles, texts = await _load_sample()
    logger.info("validation sample loaded", extra={"n": len(texts)})

    for model in CANDIDATES:
        vectors = await _embed_all(model, texts)
        reduced = umap_reduce(vectors)
        labels, _ = hdbscan_cluster(reduced)
        signals = cluster_quality_signals(labels)
        logger.info(
            "candidate signals",
            extra={"model": model, "returned_dims": int(vectors.shape[1]), **signals},
        )
        for cid in sorted(set(labels.tolist()) - {-1})[:5]:
            members = [titles[i] for i in range(len(titles)) if labels[i] == cid][:6]
            logger.info("sample cluster", extra={"model": model, "cluster": int(cid), "titles": members})


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Smoke-check the script imports (no live call)**

Run: `./.venv/bin/python -c "import ast; ast.parse(open('scripts/validate_embeddings.py').read())"`
Expected: no output (parses clean). Do NOT execute `main()` here — it makes live API calls and is operator-run during the cutover session.

- [ ] **Step 7: Lint**

Run: `./.venv/bin/python -m ruff check packages/clustering/src/clustering/quality.py packages/clustering/tests/test_quality.py scripts/validate_embeddings.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add packages/clustering/src/clustering/quality.py \
        packages/clustering/tests/test_quality.py \
        scripts/validate_embeddings.py
git commit -m "feat(clustering): embedding quality-validation gate + signals helper (SP3)"
```

---

### Task 5: `.env.example`, docs, and image confirmation

**Files:**
- Modify: `backend/.env.example` (EMBEDDING_PROVIDER block)
- Modify: `docs/llm-models.md` (embedding local|api row + re-embed/validation procedure)
- Modify: `docs/operations-sop.md` (reembed + validation runbook)
- Modify: `CLAUDE.md` (embedding module note + endpoint/CLI mention) — only if accurate after reading
- Verify (no change expected): `backend/Dockerfile` pipeline-build already copies `packages/llm/src` and `packages/embedding/src`.

- [ ] **Step 1: Confirm the image already carries `llm` for `embedding`**

Run: `grep -n "packages/llm/src\|packages/embedding/src" Dockerfile`
Expected: both appear under `pipeline-build` (lines ~105 and ~107). No Dockerfile change needed — `embedding → llm` is already importable in the pipeline image (declared as a dep in Task 2; present via the workspace). If `packages/llm/src` is NOT under `pipeline-build`, add `COPY packages/llm/src packages/llm/src` there.

- [ ] **Step 2: Add the EMBEDDING_PROVIDER block to `.env.example`**

In `backend/.env.example`, immediately after the existing `EMBEDDING_MODEL_VERSION=` line (the ML model identifiers block), add:

```bash
# --- Embedding backend (SP3) ---
# "local" = on-box embeddinggemma (torch, ~2GB RAM). "api" = OpenRouter /embeddings
# (no torch loaded — needed for low-RAM hosts). vector(768) is fixed either way.
EMBEDDING_PROVIDER=local
# OpenRouter embeddings reuse the SAME account/key as chat. dimensions=768 keeps vector(768).
EMBEDDING_API_BASE_URL=https://openrouter.ai/api/v1
EMBEDDING_API_KEY=
EMBEDDING_API_MODEL=openai/text-embedding-3-large
EMBEDDING_API_DIMENSIONS=768
EMBEDDING_REQUEST_TIMEOUT_SECONDS=60
# Optional OpenRouter attribution headers:
EMBEDDING_ATTRIBUTION_REFERER=
EMBEDDING_ATTRIBUTION_TITLE=
```

- [ ] **Step 3: Document the model table + procedure in `docs/llm-models.md`**

Read `docs/llm-models.md` first. Update the embedding entry so it states: model is config-driven (`local` = `google/embeddinggemma-300m`; `api` = `openai/text-embedding-3-large` @ 768 via OpenRouter), `vector(768)` fixed via the `dimensions` param, and that switching providers for an existing DB requires the re-embed + validation procedure. Add a short "Embedding re-embed (SP3)" subsection with the two commands:

```text
1. Validate (non-destructive, human go/no-go):
   cd backend && ./.venv/bin/python scripts/validate_embeddings.py
2. Cutover (operator-gated; set EMBEDDING_PROVIDER=api first; daemon stopped):
   docker compose --profile manual run --rm pipeline reembed
   docker compose --profile manual run --rm pipeline cluster
```

- [ ] **Step 4: Add the runbook to `docs/operations-sop.md`**

Read `docs/operations-sop.md` first. Add a "Re-embed migration (SP3)" subsection capturing: stop the daemon (or rely on the `cluster_label_score` group lock that `reembed` holds), set `EMBEDDING_PROVIDER=api` + `EMBEDDING_API_KEY`, run the validation script and read the signals (n_clusters / noise_ratio / sample titles; confirm `returned_dims == 768`), get sign-off, then `reembed` followed by a fresh `cluster`. Note it is resumable and idempotent.

- [ ] **Step 5: Update `CLAUDE.md` embedding references**

Read the embedding row in the Modules table and the "One-shot pipeline step" line. Update the embedding Notes to mention `EMBEDDING_PROVIDER=local|api` (mirrors the labeling row), and add `reembed` to the one-shot pipeline step list (`ingest`, `embed`, `cluster`, `label`, `score`, `run-daily`, `reembed`). Keep edits one-line and factual.

- [ ] **Step 6: Commit**

```bash
# docs/ and CLAUDE.md are at the repo root; .env.example is under backend/ (cwd)
git add .env.example ../docs/llm-models.md ../docs/operations-sop.md ../CLAUDE.md
git commit -m "docs(embedding): document EMBEDDING_PROVIDER + reembed/validation runbook (SP3)"
```

---

## Full-suite verification (after all tasks)

Run each affected suite separately (postgres up):

```bash
docker compose up -d postgres
./.venv/bin/python -m pytest packages/llm/tests/ -q
./.venv/bin/python -m pytest packages/clustering/tests/ -q
./.venv/bin/python -m pytest packages/embedding/tests/ -q
./.venv/bin/python -m pytest packages/pipeline/tests/ -q
```

Expected: all green. (Run separately — combining suites triggers ImportPathMismatchError.)

---

## Post-merge (operator, NOT part of the code branch)

These are runtime actions the user/operator performs once the code is merged — they are the irreversible part and require the human gate:

1. Set `EMBEDDING_API_KEY` (the OpenRouter key) in production `.env`; keep `EMBEDDING_PROVIDER=local` for now.
2. Run `scripts/validate_embeddings.py`; review `returned_dims == 768`, cluster count, noise ratio, and sample cluster titles for `openai/text-embedding-3-large` vs `google/gemini-embedding-001`. **Go/no-go.**
3. On go: set `EMBEDDING_PROVIDER=api` (and the winning `EMBEDDING_API_MODEL`), stop the daemon, run `reembed`, then `cluster`. On no-go: stay `local`, reconsider model.
```
