# Full-API + Reversible-Local + Slim Deploy Image (SP4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backend run all AI (embedding, labeling, analyst) via external API by default with a slim torch/llama-cpp-free pipeline image, while keeping local inference as a reversible build-time variant, and deploy on a 2 GB VPS with Postgres off-box.

**Architecture:** Move the local-only ML libraries into PEP 621 `[local]` optional-extras so the default `uv sync` is torch-free. Split the Dockerfile `pipeline` target into two flavors — `pipeline-api` (slim, prod default) and `pipeline-local` (full ML, opt-in) — each a build/runtime/dev triple. Flip provider defaults to `api`, add fail-fast guards for misconfigured images, repurpose `docker-compose.prod.yml` to a lean external-Postgres topology, and delete dead local-only code.

**Tech Stack:** Python 3.11, uv workspace, sentence-transformers/torch (now optional), llama-cpp-python (now optional), FastAPI, SQLAlchemy async, Docker BuildKit multi-stage, docker compose v2, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-06-26-full-api-reversible-local-design.md`

## Global Constraints

Every task's requirements implicitly include these (verbatim from CLAUDE.md / `docs/docker-sop.md` / the spec):

- `vector(768)` is fixed; embeddings stay 768-dim. No schema migration in this plan.
- `api` package never imports ML modules (torch/transformers). Unchanged here.
- `torch` is pinned to the `pytorch-cpu` index in root `pyproject.toml`. **Moving torch to an extra must NOT change this pin.** After any `uv lock`, `grep -E '^name = "(nvidia|cuda|triton)' uv.lock` MUST return zero matches.
- Batch modules never import each other — share via `core` or `llm`. No new cross-module imports beyond what already exists.
- src layout per package; no flat layouts.
- All logs are JSON to stdout via `core.logging.configure_logging()`. No `print()`.
- No new top-level deps. This plan only **reclassifies** existing deps (mandatory → optional) and **removes** dead code.
- Host unit tests run with `./.venv/bin/python -m pytest …` (NOT `uv run`). Docker builds run from `backend/`.
- **uv gotcha:** `uv sync --package X` prunes the host `.venv` (strips pytest + other members). After any such command, restore the host test env with `uv sync --all-packages --all-extras` before running tests.
- All git commit messages end with the trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

All paths below are relative to `backend/` unless they start with `docs/` or `CLAUDE.md` (repo root).

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `packages/embedding/pyproject.toml` | `torch`/`sentence-transformers` → `[local]` extra | 1 |
| `packages/labeling/pyproject.toml` | `llama-cpp-python`/`huggingface-hub` → `[local]` extra | 1 |
| `packages/pipeline/pyproject.toml` | aggregate `local` extra (`embedding[local]`, `labeling[local]`) | 1 |
| `uv.lock` | regenerated lock with extras | 1 |
| `packages/pipeline/tests/test_import_graph.py` | guard: API mode imports no local ML libs | 2 |
| `packages/embedding/src/embedding/pipeline.py` | friendly RuntimeError when local extra missing | 3 |
| `packages/embedding/tests/test_pipeline.py` | guard test | 3 |
| `packages/pipeline/src/pipeline/runner.py` | startup pre-flight provider/deps check | 4 |
| `packages/pipeline/tests/test_runner.py` | pre-flight tests | 4 |
| `packages/core/src/core/config.py` | provider defaults → `api` | 5 |
| `packages/core/tests/test_config.py` | default assertion | 5 |
| `.env.example`, `CLAUDE.md` | document API-first | 5 |
| `packages/labeling/src/labeling/llm.py`, `.../prompts.py` | delete dead local-only functions | 6 |
| `packages/labeling/tests/test_llm.py` | remove dead-function tests | 6 |
| `Dockerfile` | `pipeline-api`/`pipeline-local` triples | 7 |
| `docs/docker-sop.md` | stage table + image-size budgets + extras rule | 7, 8 |
| `docker-compose.prod.yml` | lean 2 GB external-PG topology | 8 |
| `docker-compose.yml` | dev target refs `pipeline-dev` → `pipeline-api-dev` | 8 |
| `docs/operations-sop.md` | API ⇄ local switch runbook | 9 |

---

### Task 1: Reclassify ML deps into `[local]` extras

**Files:**
- Modify: `packages/embedding/pyproject.toml`
- Modify: `packages/labeling/pyproject.toml`
- Modify: `packages/pipeline/pyproject.toml`
- Modify: `uv.lock` (regenerated)

**Interfaces:**
- Produces: extra `local` on `embedding`, `labeling`, and `pipeline`. `uv sync --package pipeline` → torch-free; `uv sync --package pipeline --extra local` → torch + llama-cpp present.

- [ ] **Step 1: Edit `packages/embedding/pyproject.toml`** — move the two ML libs out of `dependencies` into a `local` extra.

Replace the `dependencies` list and add the extra:
```toml
dependencies = [
  "core",
  "llm",
  "numpy>=1.26",
  "click>=8.1",
]

[project.optional-dependencies]
local = [
  "sentence-transformers>=3.2",
  "torch>=2.4",
]
```
(Leave `[tool.uv.sources]`, `[build-system]`, `[tool.hatch...]` untouched.)

- [ ] **Step 2: Edit `packages/labeling/pyproject.toml`** — same pattern.

```toml
dependencies = [
  "core",
  "llm",
  "numpy>=1.26",
  "click>=8.1",
]

[project.optional-dependencies]
local = [
  "llama-cpp-python>=0.3",
  "huggingface-hub>=0.30",
]
```

- [ ] **Step 3: Edit `packages/pipeline/pyproject.toml`** — add an aggregate extra after the `dependencies` list.

```toml
[project.optional-dependencies]
local = [
  "embedding[local]",
  "labeling[local]",
]
```

- [ ] **Step 4: Relock**

Run: `uv lock`
Expected: completes successfully, `uv.lock` updated.

- [ ] **Step 5: Verify the API path is torch-free and the local extra still resolves**

```bash
# Slim resolution: torch must NOT be installed
uv sync --package pipeline --no-dev --frozen
.venv/bin/python -c "import importlib.util; assert importlib.util.find_spec('torch') is None, 'torch leaked into slim sync'; assert importlib.util.find_spec('llama_cpp') is None, 'llama_cpp leaked'; print('slim OK')"

# Local resolution: torch + llama_cpp present
uv sync --package pipeline --extra local --no-dev --frozen
.venv/bin/python -c "import importlib.util; assert importlib.util.find_spec('torch'); assert importlib.util.find_spec('llama_cpp'); print('local OK')"
```
Expected: `slim OK` then `local OK`.

If `--extra local` fails to resolve `embedding[local]`/`labeling[local]` transitively, fall back to listing the leaf libs directly in `pipeline`'s `local` extra (`"sentence-transformers>=3.2"`, `"torch>=2.4"`, `"llama-cpp-python>=0.3"`, `"huggingface-hub>=0.30"`), re-run `uv lock`, and repeat this step.

- [ ] **Step 6: Verify no CUDA wheels leaked**

Run: `grep -E '^name = "(nvidia|cuda|triton)' uv.lock`
Expected: no output (exit 1).

- [ ] **Step 7: Restore the host test env** (the `--package` syncs above pruned it)

Run: `uv sync --all-packages --all-extras`
Expected: completes; `./.venv/bin/python -m pytest --version` works.

- [ ] **Step 8: Commit**

```bash
git add packages/embedding/pyproject.toml packages/labeling/pyproject.toml packages/pipeline/pyproject.toml uv.lock
git commit -m "build(deps): move torch/sentence-transformers/llama-cpp into [local] extras

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Import-graph invariant guard (API mode is torch-free)

**Files:**
- Create: `packages/pipeline/tests/test_import_graph.py`

**Interfaces:**
- Consumes: the lazy-import structure of `embedding.pipeline` and `labeling.llm` (unchanged by this task).

- [ ] **Step 1: Write the test** (regression guard — codifies the invariant)

```python
import subprocess
import sys
import textwrap


def test_api_mode_imports_no_local_ml_libs():
    """Importing the embedding/labeling code paths with providers=api must not
    pull torch/sentence-transformers/llama-cpp/huggingface-hub into sys.modules.
    Runs in a subprocess so sys.modules is clean and unaffected by the test runner."""
    script = textwrap.dedent(
        """
        import os, sys
        os.environ["EMBEDDING_PROVIDER"] = "api"
        os.environ["LABELING_PROVIDER"] = "api"
        os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
        import embedding.pipeline  # noqa: F401
        import labeling.llm        # noqa: F401
        forbidden = {"torch", "sentence_transformers", "llama_cpp", "huggingface_hub"}
        leaked = forbidden & set(sys.modules)
        assert not leaked, f"local ML libs imported in API mode: {sorted(leaked)}"
        print("OK")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
```

- [ ] **Step 2: Run the test**

Run: `./.venv/bin/python -m pytest packages/pipeline/tests/test_import_graph.py -v`
Expected: PASS (the lazy-import structure already satisfies the invariant; this test locks it in). If it FAILS, a top-level ML import has leaked — fix the offending module before continuing.

- [ ] **Step 3: Commit**

```bash
git add packages/pipeline/tests/test_import_graph.py
git commit -m "test(pipeline): guard API mode against importing local ML libs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Embedding fail-fast guard when local extra is missing

**Files:**
- Modify: `packages/embedding/src/embedding/pipeline.py` (`_encode_local`, currently lines 27-31)
- Test: `packages/embedding/tests/test_pipeline.py`

**Interfaces:**
- Produces: `_encode_local` raises `RuntimeError` (message contains `pipeline-local`) when `embedding.embedder` cannot be imported, instead of a raw `ImportError`/`ModuleNotFoundError`.

- [ ] **Step 1: Write the failing test**

Add to `packages/embedding/tests/test_pipeline.py`:
```python
import sys

import pytest


async def test_encode_local_missing_extra_raises_actionable(monkeypatch):
    import embedding.pipeline as ep

    monkeypatch.setattr(ep.settings, "embedding_provider", "local")
    # Simulate the local extra being absent: importing embedding.embedder fails.
    monkeypatch.setitem(sys.modules, "embedding.embedder", None)

    with pytest.raises(RuntimeError, match="pipeline-local"):
        await ep._encode(["hello world"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python -m pytest "packages/embedding/tests/test_pipeline.py::test_encode_local_missing_extra_raises_actionable" -v`
Expected: FAIL — raises `ImportError` (not `RuntimeError`), so `pytest.raises(RuntimeError)` does not match.

- [ ] **Step 3: Implement the guard**

In `packages/embedding/src/embedding/pipeline.py`, replace `_encode_local` (lines 27-31):
```python
def _encode_local(texts: list[str]) -> np.ndarray:
    try:
        from embedding.embedder import get_embedder
    except ImportError as exc:
        raise RuntimeError(
            "EMBEDDING_PROVIDER=local but the local extra is not installed "
            "(torch/sentence-transformers missing). Deploy the pipeline-local "
            "image or set EMBEDDING_PROVIDER=api."
        ) from exc

    embedder = get_embedder()
    return embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/python -m pytest "packages/embedding/tests/test_pipeline.py::test_encode_local_missing_extra_raises_actionable" -v`
Expected: PASS.

- [ ] **Step 5: Run the full embedding suite (no regressions)**

Run: `./.venv/bin/python -m pytest packages/embedding/tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/embedding/src/embedding/pipeline.py packages/embedding/tests/test_pipeline.py
git commit -m "feat(embedding): actionable error when provider=local but extra missing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Pipeline startup pre-flight provider/deps check

**Files:**
- Modify: `packages/pipeline/src/pipeline/runner.py` (add `_preflight_provider_deps`; call it in `run_loop`, currently starts line 342)
- Test: `packages/pipeline/tests/test_runner.py` (create if absent)

**Interfaces:**
- Consumes: `settings.embedding_provider`, `settings.labeling_provider`.
- Produces: `pipeline.runner._preflight_provider_deps() -> None` — raises `RuntimeError` (message contains `pipeline-local`) at startup if a `local` provider's libs are not importable; no-op and imports nothing when both providers are `api`.

- [ ] **Step 1: Write the failing tests**

Create/append `packages/pipeline/tests/test_runner.py`:
```python
import sys

import pytest


def test_preflight_api_mode_imports_nothing(monkeypatch):
    from pipeline import runner

    monkeypatch.setattr(runner.settings, "embedding_provider", "api")
    monkeypatch.setattr(runner.settings, "labeling_provider", "api")
    # If pre-flight tried to import these, the None entries would raise ImportError.
    monkeypatch.setitem(sys.modules, "embedding.embedder", None)
    monkeypatch.setitem(sys.modules, "llama_cpp", None)

    runner._preflight_provider_deps()  # must not raise


def test_preflight_local_missing_dep_raises(monkeypatch):
    from pipeline import runner

    monkeypatch.setattr(runner.settings, "embedding_provider", "local")
    monkeypatch.setattr(runner.settings, "labeling_provider", "api")
    monkeypatch.setitem(sys.modules, "embedding.embedder", None)

    with pytest.raises(RuntimeError, match="pipeline-local"):
        runner._preflight_provider_deps()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/bin/python -m pytest packages/pipeline/tests/test_runner.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.runner' has no attribute '_preflight_provider_deps'`.

- [ ] **Step 3: Implement the pre-flight function**

In `packages/pipeline/src/pipeline/runner.py`, add after the module logger (near line 27):
```python
def _preflight_provider_deps() -> None:
    """Fail fast at startup if a provider is set to 'local' but the local extra
    is not installed in this image (e.g. running the slim pipeline-api image
    with EMBEDDING_PROVIDER=local)."""
    if settings.embedding_provider == "local":
        try:
            import embedding.embedder  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=local but the local extra is not installed. "
                "Deploy the pipeline-local image or set EMBEDDING_PROVIDER=api."
            ) from exc
    if settings.labeling_provider == "local":
        try:
            import llama_cpp  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "LABELING_PROVIDER=local but the local extra is not installed. "
                "Deploy the pipeline-local image or set LABELING_PROVIDER=api."
            ) from exc
```

- [ ] **Step 4: Wire it into `run_loop`**

In `run_loop` (line 342), add the call immediately after `_install_signal_handlers(shutdown)` (line 347):
```python
    shutdown = asyncio.Event()
    _install_signal_handlers(shutdown)

    _preflight_provider_deps()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./.venv/bin/python -m pytest packages/pipeline/tests/test_runner.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add packages/pipeline/src/pipeline/runner.py packages/pipeline/tests/test_runner.py
git commit -m "feat(pipeline): startup pre-flight fails fast on local provider w/o extra

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Flip provider defaults to `api` + docs

**Files:**
- Modify: `packages/core/src/core/config.py` (line 68 `labeling_provider`, line 77 `embedding_provider`)
- Test: `packages/core/tests/test_config.py` (create if absent)
- Modify: `.env.example` (lines 23, 95)
- Modify: `CLAUDE.md` (Modules table `embedding`/`labeling` rows; §Pipeline runtime; §Quickstart)

**Interfaces:**
- Produces: `Settings()` defaults `embedding_provider == "api"` and `labeling_provider == "api"`.

- [ ] **Step 1: Write the failing test**

Create/append `packages/core/tests/test_config.py`:
```python
def test_provider_defaults_are_api(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("LABELING_PROVIDER", raising=False)
    from core.config import Settings

    s = Settings(database_url="postgresql+asyncpg://x:x@localhost/x", _env_file=None)
    assert s.embedding_provider == "api"
    assert s.labeling_provider == "api"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/bin/python -m pytest packages/core/tests/test_config.py::test_provider_defaults_are_api -v`
Expected: FAIL — defaults are currently `"local"`.

- [ ] **Step 3: Flip the defaults**

In `packages/core/src/core/config.py`:
- Line 68: `labeling_provider: str = "local"` → `labeling_provider: str = "api"`
- Line 77: `embedding_provider: str = "local"` → `embedding_provider: str = "api"`

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/python -m pytest packages/core/tests/test_config.py::test_provider_defaults_are_api -v`
Expected: PASS.

- [ ] **Step 5: Update `.env.example`**

- Line 23: `EMBEDDING_PROVIDER=local` → `EMBEDDING_PROVIDER=api`
- Line 95: `LABELING_PROVIDER=local` → `LABELING_PROVIDER=api`

Add a comment line directly above each documenting the local alternative, e.g. above line 23:
```
# Set to "local" ONLY with the pipeline-local image (bundles torch/sentence-transformers).
```
and above the labeling line:
```
# Set to "local" ONLY with the pipeline-local image (bundles Gemma GGUF via llama-cpp).
```

- [ ] **Step 6: Update `CLAUDE.md`**

- Modules table `embedding` row: change note to `…; EMBEDDING_PROVIDER=api (default)|local`.
- Modules table `labeling` row: change note to `LLM cluster labels via shared llm package; LABELING_PROVIDER=api (default)|local (Gemma 2B GGUF)`.
- §Pipeline runtime: in the reactive-embed bullet, note that embedding/labeling default to the API path; the local path requires the `pipeline-local` image.
- §Quickstart: add a one-shot pipeline note that the manual profile uses the `pipeline-api` image.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/core/config.py packages/core/tests/test_config.py .env.example CLAUDE.md
git commit -m "feat(config): default embedding/labeling providers to api

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Delete dead local-only labeling functions

**Files:**
- Modify: `packages/labeling/src/labeling/llm.py` (remove `generate_label_and_insight` lines 238-281, `extract_article_claims` lines 289-304, `deduplicate_claims` lines 307-319, and helper `_clean_line` lines 284-286 if exclusively used by them)
- Modify: `packages/labeling/src/labeling/prompts.py` (remove `format_insight_messages`, `format_extract_messages`, `format_dedup_messages` if exclusively used by the deleted functions)
- Modify: `packages/labeling/tests/test_llm.py` (remove tests for the deleted functions)

**Interfaces:**
- Consumes: nothing new.
- Produces: `labeling.llm` exposes only the still-used API/local label paths (`generate_label`, `generate_cluster_insight`, and their helpers `get_llm`, `_chat`, `_label_local`, `_cluster_insight_local`, `_parse_cluster_insight`, `_strip_label`).

- [ ] **Step 1: Confirm the three functions are unused outside tests**

Run: `grep -rn -E "generate_label_and_insight|extract_article_claims|deduplicate_claims" packages --include="*.py" | grep -v "/tests/"`
Expected: only their `def` lines in `packages/labeling/src/labeling/llm.py` (no production callers). If any non-test, non-def caller appears, STOP and reassess.

- [ ] **Step 2: Delete the three functions from `llm.py`**

Remove `generate_label_and_insight`, `extract_article_claims`, `deduplicate_claims` (lines 238-319 region) from `packages/labeling/src/labeling/llm.py`. In the same file, remove the now-orphaned names `format_dedup_messages`, `format_extract_messages`, and `format_insight_messages` from the `from labeling.prompts import (...)` block (lines 11-19), keeping `format_cluster_insight_messages`, `format_cluster_insight_messages_api`, `format_label_messages_api`, and `format_messages`.

- [ ] **Step 3: Remove `_clean_line` only if now-orphaned**

Run: `grep -n "_clean_line" packages/labeling/src/labeling/llm.py`
Expected after Step 2: no remaining references → delete the `_clean_line` definition (lines 284-286). If references remain, leave it.

- [ ] **Step 4: Remove orphaned prompt builders**

For each of `format_insight_messages`, `format_extract_messages`, `format_dedup_messages`:
Run: `grep -rn "<name>" packages --include="*.py" | grep -v "def <name>"`
If the only remaining references are in `test_llm.py` (which Step 5 removes) and the deleted functions, delete that builder from `packages/labeling/src/labeling/prompts.py`. Keep `format_messages`, `format_cluster_insight_messages`, `format_cluster_insight_messages_api`, `format_label_messages_api` (still used).

- [ ] **Step 5: Remove the dead-function tests**

In `packages/labeling/tests/test_llm.py`, remove the imports and test functions covering `extract_article_claims`, `deduplicate_claims`, and `generate_label_and_insight` (the `# ── extract_article_claims` and `# ── deduplicate_claims` sections and any `generate_label_and_insight` tests). Leave tests for `generate_label`, `generate_cluster_insight`, and parsing helpers.

- [ ] **Step 6: Run the labeling suite + import check**

```bash
./.venv/bin/python -m pytest packages/labeling/tests/ -v
./.venv/bin/python -c "import labeling.llm, labeling.prompts; print('import OK')"
```
Expected: PASS, then `import OK`.

- [ ] **Step 7: Commit**

```bash
git add packages/labeling/src/labeling/llm.py packages/labeling/src/labeling/prompts.py packages/labeling/tests/test_llm.py
git commit -m "refactor(labeling): drop dead local-only claim/insight functions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Split the Dockerfile into `pipeline-api` / `pipeline-local` triples

**Files:**
- Modify: `Dockerfile` (replace the pipeline section, lines 96-162)
- Modify: `docs/docker-sop.md` (§Multi-stage targets table; §Image-size budgets)

**Interfaces:**
- Consumes: the `local` extra from Task 1.
- Produces: build targets `pipeline-api`, `pipeline-api-dev`, `pipeline-local`, `pipeline-local-dev` (and intermediate `pipeline-src`, `pipeline-api-build`, `pipeline-local-build`, `pipeline-runtime-base`). The `pipeline`/`pipeline-build`/`pipeline-dev` stage names are retired.

- [ ] **Step 1: Replace the pipeline section in `Dockerfile`**

Delete the current `pipeline-build` / `pipeline` / `pipeline-dev` stages (lines 96-162) and insert:

```dockerfile
# ============ Pipeline shared source (both flavors) ============
FROM deps AS pipeline-src
# Chromium system dependencies required by Playwright (fallback scraper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*
COPY packages/core/src        packages/core/src
COPY packages/llm/src         packages/llm/src
COPY packages/ingest/src      packages/ingest/src
COPY packages/embedding/src   packages/embedding/src
COPY packages/clustering/src  packages/clustering/src
COPY packages/labeling/src    packages/labeling/src
COPY packages/scoring/src     packages/scoring/src
COPY packages/pipeline/src    packages/pipeline/src

# ---- API-flavor build: slim, no torch/llama-cpp ----
FROM pipeline-src AS pipeline-api-build
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package pipeline --no-dev --frozen
ENV PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers
RUN .venv/bin/playwright install chromium

# ---- Local-flavor build: full ML stack via the [local] extra ----
FROM pipeline-src AS pipeline-local-build
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package pipeline --extra local --no-dev --frozen
ENV PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers
RUN .venv/bin/playwright install chromium

# ============ Pipeline runtime base (shared apt + ENV) ============
FROM python:3.11-slim AS pipeline-runtime-base
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libgomp1 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# OMP/BLAS thread caps keep numpy/UMAP (and Gemma in the local flavor) from
# saturating all host cores.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers \
    OMP_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    NUMEXPR_NUM_THREADS=4 \
    TOKENIZERS_PARALLELISM=false
ENTRYPOINT ["python", "-m", "pipeline.cli"]
CMD ["run-daily"]

# ============ pipeline-api: slim runtime (prod default) ============
FROM pipeline-runtime-base AS pipeline-api
COPY --from=pipeline-api-build /app/.venv               /app/.venv
COPY --from=pipeline-api-build /app/packages            /app/packages
COPY --from=pipeline-api-build /app/playwright-browsers /app/playwright-browsers
ENV EMBEDDING_PROVIDER=api \
    LABELING_PROVIDER=api

# ============ pipeline-api-dev: venv-only, source bind-mounted ============
FROM pipeline-runtime-base AS pipeline-api-dev
COPY --from=pipeline-api-build /app/.venv               /app/.venv
COPY --from=pipeline-api-build /app/playwright-browsers /app/playwright-browsers
ENV EMBEDDING_PROVIDER=api \
    LABELING_PROVIDER=api

# ============ pipeline-local: full ML runtime (opt-in) ============
FROM pipeline-runtime-base AS pipeline-local
COPY --from=pipeline-local-build /app/.venv               /app/.venv
COPY --from=pipeline-local-build /app/packages            /app/packages
COPY --from=pipeline-local-build /app/playwright-browsers /app/playwright-browsers
ENV EMBEDDING_PROVIDER=local \
    LABELING_PROVIDER=local

# ============ pipeline-local-dev: venv-only, source bind-mounted ============
FROM pipeline-runtime-base AS pipeline-local-dev
COPY --from=pipeline-local-build /app/.venv               /app/.venv
COPY --from=pipeline-local-build /app/playwright-browsers /app/playwright-browsers
ENV EMBEDDING_PROVIDER=local \
    LABELING_PROVIDER=local
```

- [ ] **Step 2: Build the slim API target and verify it is torch-free**

```bash
DOCKER_BUILDKIT=1 docker build --target pipeline-api -t ei-pipeline-api:test .
docker run --rm ei-pipeline-api:test \
  python -c "import importlib.util as u; assert u.find_spec('torch') is None and u.find_spec('llama_cpp') is None; print('slim image OK')"
```
Expected: `slim image OK`.

- [ ] **Step 3: Verify API mode imports no ML libs inside the image**

```bash
docker run --rm -e EMBEDDING_PROVIDER=api -e LABELING_PROVIDER=api \
  -e DATABASE_URL=postgresql+asyncpg://x:x@localhost/x ei-pipeline-api:test \
  python -c "import sys, embedding.pipeline, labeling.llm; \
assert not ({'torch','sentence_transformers','llama_cpp','huggingface_hub'} & set(sys.modules)); print('graph OK')"
```
Expected: `graph OK`.

- [ ] **Step 4: Build the local target and verify torch is present**

```bash
DOCKER_BUILDKIT=1 docker build --target pipeline-local -t ei-pipeline-local:test .
docker run --rm ei-pipeline-local:test python -c "import torch, llama_cpp; print('local image OK')"
```
Expected: `local image OK`.

- [ ] **Step 5: Check image sizes against budget**

```bash
docker images | grep -E "ei-pipeline-(api|local)"
```
Expected: `pipeline-api` ≤ ~1.2 GB; `pipeline-local` ≤ 6 GB. If `pipeline-api` exceeds the budget, run `docker history ei-pipeline-api:test` and remove the leaked dependency before continuing.

- [ ] **Step 6: Verify second-build layer cache hits**

```bash
DOCKER_BUILDKIT=1 docker build --target pipeline-api -t ei-pipeline-api:test . 2>&1 | grep -E "CACHED|uv sync --no-install-workspace"
```
Expected: the `deps` `uv sync --no-install-workspace` layer is `CACHED`.

- [ ] **Step 7: Update `docs/docker-sop.md`**

- §Multi-stage targets table: remove the `pipeline-build` / `pipeline` / `pipeline-dev` rows; add `pipeline-src`, `pipeline-api-build`, `pipeline-api`, `pipeline-api-dev`, `pipeline-local-build`, `pipeline-local`, `pipeline-local-dev` with purposes (API flavor = slim/no torch; local flavor = full ML via `[local]` extra). Note the prod daemon uses `pipeline-api`.
- §Image-size budgets table: keep `api ≤ 250MB`; replace the `pipeline ≤ 6GB` row with `pipeline-api ≤ 1.2GB` (no torch/llama-cpp) and `pipeline-local ≤ 6GB`.
- Add a short rule under §Multi-stage targets: "Local-only ML libs (`torch`, `sentence-transformers`, `llama-cpp-python`, `huggingface-hub`) live in each module's `[local]` extra and are installed **only** in `*-local-build` via `uv sync --package pipeline --extra local`. The API flavor must never carry them."

- [ ] **Step 8: Commit**

```bash
git add Dockerfile docs/docker-sop.md
git commit -m "build(docker): split pipeline into slim pipeline-api + opt-in pipeline-local

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Repurpose prod compose to lean 2 GB topology + fix dev target refs

**Files:**
- Modify: `docker-compose.prod.yml`
- Modify: `docker-compose.yml` (dev service `target:` refs)
- Modify: `docs/docker-sop.md` (§Compose conventions → Prod)

**Interfaces:**
- Consumes: Dockerfile targets `api`, `pipeline-api`, `pipeline-api-dev` from Task 7.

- [ ] **Step 1: Rewrite `docker-compose.prod.yml`** — remove the bundled `postgres` service, point `DATABASE_URL` at an external host, build the slim targets, set tight `mem_limit`s, add healthchecks.

```yaml
name: editor-intelligence

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: api
    environment:
      DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    ports:
      - "127.0.0.1:8000:8000"
    mem_limit: 512m
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "python -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8000/api/v1/health\").read()'"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  pipeline-daemon:
    build:
      context: .
      dockerfile: Dockerfile
      target: pipeline-api
    environment:
      DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      TIMEZONE: ${TIMEZONE:-Asia/Jakarta}
      CLUSTER_SCHEDULE_HOUR: ${CLUSTER_SCHEDULE_HOUR:-6}
      CLUSTER_SCHEDULE_MINUTE: ${CLUSTER_SCHEDULE_MINUTE:-0}
      CLUSTERING_WINDOW_DAYS: ${CLUSTERING_WINDOW_DAYS:-7}
      INGEST_TIMEOUT_SECONDS: ${INGEST_TIMEOUT_SECONDS:-30}
      EMBEDDING_PROVIDER: ${EMBEDDING_PROVIDER:-api}
      EMBEDDING_API_KEY: ${EMBEDDING_API_KEY:?EMBEDDING_API_KEY is required}
      LABELING_PROVIDER: ${LABELING_PROVIDER:-api}
      LABELING_LLM_API_KEY: ${LABELING_LLM_API_KEY:?LABELING_LLM_API_KEY is required}
    mem_limit: 1g
    restart: always
    stop_grace_period: 30s
    command: ["serve"]
    healthcheck:
      test: ["CMD-SHELL", "pgrep -f 'pipeline.cli serve' >/dev/null"]
      interval: 30s
      timeout: 5s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  pipeline:
    build:
      context: .
      dockerfile: Dockerfile
      target: pipeline-api
    environment:
      DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      TIMEZONE: ${TIMEZONE:-Asia/Jakarta}
      EMBEDDING_PROVIDER: ${EMBEDDING_PROVIDER:-api}
      EMBEDDING_API_KEY: ${EMBEDDING_API_KEY:-}
      LABELING_PROVIDER: ${LABELING_PROVIDER:-api}
      LABELING_LLM_API_KEY: ${LABELING_LLM_API_KEY:-}
    profiles:
      - manual
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```
(No `postgres` service, no `pgdata`/`hfcache` volumes — the slim API image needs neither an HF model cache nor a co-located DB.)

- [ ] **Step 2: Validate the prod compose**

Run: `DATABASE_URL=postgresql+asyncpg://x:x@db.example/x EMBEDDING_API_KEY=x LABELING_LLM_API_KEY=x docker compose -f docker-compose.prod.yml config >/dev/null && echo "prod config OK"`
Expected: `prod config OK` (no missing-variable errors, valid YAML).

- [ ] **Step 3: Fix dev target refs in `docker-compose.yml`**

Change every pipeline service `target: pipeline-dev` to `target: pipeline-api-dev` (the `pipeline-daemon` and `pipeline` services; the `api` service keeps `target: api-dev`). To run the local path in dev, an operator switches that service's target to `pipeline-local-dev` manually.

- [ ] **Step 4: Validate the dev compose**

Run: `docker compose config >/dev/null && echo "dev config OK"`
Expected: `dev config OK`.

- [ ] **Step 5: Update `docs/docker-sop.md` §Compose conventions → Prod**

Document: no bundled Postgres (external `DATABASE_URL`); `pipeline-daemon`/`pipeline` build `pipeline-api`; `mem_limit` `api: 512m`, `pipeline-daemon: 1g` (verify with `docker stats`); required API keys via `${VAR:?}`; healthchecks present. Replace the stale "`pipeline-daemon` has `deploy.resources.limits.memory: 3g`" line and the dev "`build target is the `*-dev` variant`" line to reference the new targets.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.prod.yml docker-compose.yml docs/docker-sop.md
git commit -m "build(compose): lean 2GB prod topology (external PG, slim pipeline-api, mem_limits)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: API ⇄ local switch runbook in operations SOP

**Files:**
- Modify: `docs/operations-sop.md`

**Interfaces:**
- Consumes: the reembed CLI + validation script from SP3 (referenced, not changed).

- [ ] **Step 1: Add a "Switching inference backend (API ⇄ local)" section to `docs/operations-sop.md`**

Include both procedures verbatim from the spec §6:

```markdown
## Switching inference backend (API ⇄ local)

The pipeline ships in two image flavors: `pipeline-api` (slim, default — embedding
and labeling go to the external API) and `pipeline-local` (full ML on-box). Switching
is a redeploy, not a live env flip — the slim image does not contain torch/llama-cpp.

### local → API (the 2 GB default)
1. Set `EMBEDDING_API_KEY` and `LABELING_LLM_API_KEY` (OpenRouter) in the prod `.env`.
2. Run `backend/scripts/validate_embeddings.py`; confirm `returned_dims == 768` and the
   cluster-quality signals; get human go/no-go.
3. **Stop the daemon** (mandatory — the group lock does not block the reactive embed loop).
4. Set `EMBEDDING_PROVIDER=api` / `LABELING_PROVIDER=api`, then run
   `docker compose --profile manual run --rm pipeline reembed` and then `… cluster`.
5. Deploy the `pipeline-api` image (`docker compose -f docker-compose.prod.yml up -d`).

### API → local (re-enable on-box inference)
1. Build/deploy the `pipeline-local` image (set the pipeline service `target: pipeline-local`),
   mount a model-cache volume at `/models`.
2. Set `EMBEDDING_PROVIDER=local` / `LABELING_PROVIDER=local` (the image already bakes these).
3. If the local embedding model differs from the rows in DB, stop the daemon and run
   `reembed` then `cluster`.
4. Restart the daemon.
```

- [ ] **Step 2: Verify markdown renders cleanly**

Run: `grep -n "Switching inference backend" docs/operations-sop.md`
Expected: the new heading is present.

- [ ] **Step 3: Commit**

```bash
git add docs/operations-sop.md
git commit -m "docs(ops): runbook for switching inference backend API <-> local

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (after all tasks)

- [ ] Full host test suite: `uv sync --all-packages --all-extras && ./.venv/bin/python -m pytest packages/ -q` (the pre-existing `pipeline test_e2e.py::test_e2e_pipeline_and_api` `/clusters/morning` failure is known and out of scope — see the migration memory).
- [ ] Both images build: `DOCKER_BUILDKIT=1 docker build --target pipeline-api . && DOCKER_BUILDKIT=1 docker build --target pipeline-local .`
- [ ] CUDA-free: `grep -E '^name = "(nvidia|cuda|triton)' uv.lock` → no output.
- [ ] `pipeline-api` image size within budget (`docker images | grep ei-pipeline`).
