# Design — Full-API inference with reversible-to-local + slim deploy image (SP4)

Date: 2026-06-26
Status: Approved (design); implementation plan to follow.
Builds on: `[[project-full-api-2gb-migration]]` (SP1 shared `llm` pkg, SP2 labeling→API, SP3 embedding→API — all merged). This is **SP4** plus formalizing the dual-mode (API ⇄ local) contract.

## 1. Problem

The backend can already run embedding and labeling via an external AI API (SP2/SP3), but:

1. **Defaults are still `local`** (`embedding_provider=local`, `labeling_provider=local`), so a default deploy still loads `torch` + Gemma GGUF on CPU.
2. **Heavy ML libs are mandatory dependencies** (`torch`, `sentence-transformers` in `embedding`; `llama-cpp-python`, `huggingface-hub` in `labeling`). The `pipeline` image therefore bundles ~2 GB+ of ML wheels even when running in API mode — failing the 2 GB VPS goal on image hygiene and forcing the layer cache to carry them.
3. **`docker-compose.prod.yml` co-locates Postgres** on the same box and sets a memory limit far above 2 GB.
4. **Dead local-only code** in `labeling/llm.py` (`extract_article_claims`, `deduplicate_claims`, `generate_label_and_insight`) hard-wires `llama_cpp` with no API branch — a landmine in an API-only image.

## 2. Goals

- Ship a **slim, API-only pipeline image** that contains **no** `torch`/`sentence-transformers`/`llama-cpp-python`/`huggingface-hub`.
- Keep **local inference fully reversible** as a **build-time variant** (`pipeline-local` image), not a runtime env flip — switching back to local = rebuild/redeploy the local image + set provider env.
- Make the **2 GB VPS deploy** real: Postgres off-box, tight per-service `mem_limit`, healthchecks.
- Preserve every existing hard rule: `vector(768)` unchanged, `api` image ML-free, torch pinned to the CPU index (no CUDA wheels), src layout, JSON logging.

## 3. Non-goals

- No change to embedding dimensions or DB schema (`vector(768)` stays; OpenRouter embeddings honor `dimensions=768`).
- No removal of Playwright/Chromium from the pipeline image — the fallback scraper uses it and it is **not** "unused local LLM". It stays in both pipeline variants.
- No change to clustering (UMAP+HDBSCAN remains the only intended local compute), scoring, or `api`/`analyst` runtime behavior.
- No production orchestration (k8s/Swarm), TLS/reverse-proxy, CI/CD, or secret distribution — owned externally per `docs/docker-sop.md` §"What this SOP does not cover".

## 4. Locked decisions

| # | Decision |
|---|---|
| D1 | Two named runtime targets: **`pipeline-api`** (slim, prod default) and **`pipeline-local`** (full ML, opt-in). Each gets a build/runtime/dev triple. |
| D2 | Flip code default to **`api`** in `core/config.py` and `.env.example`. The `pipeline-local` image bakes `ENV …PROVIDER=local`. |
| D3 | **Repurpose `docker-compose.prod.yml`** into the lean 2 GB topology (Postgres off-box, slim targets, tight `mem_limit`). No third compose file. |
| D4 | **Delete** the dead local-only functions in `labeling/llm.py` and their tests. |

## 5. Architecture

### 5.1 Dependency strategy — PEP 621 optional-extras

Move the local-only ML libs out of mandatory `dependencies` into a `[project.optional-dependencies]` extra named `local`. `numpy` stays mandatory (used by the API paths and clustering math).

`packages/embedding/pyproject.toml`
```toml
[project]
dependencies = ["core", "llm", "numpy>=1.26", "click>=8.1"]

[project.optional-dependencies]
local = ["sentence-transformers>=3.2", "torch>=2.4"]
```

`packages/labeling/pyproject.toml`
```toml
[project]
dependencies = ["core", "llm", "numpy>=1.26", "click>=8.1"]

[project.optional-dependencies]
local = ["llama-cpp-python>=0.3", "huggingface-hub>=0.30"]
```

`packages/pipeline/pyproject.toml` — aggregate the extras so a single `--extra local` pulls both:
```toml
[project.optional-dependencies]
local = ["embedding[local]", "labeling[local]"]
```

**Unchanged and required:** the root `pyproject.toml` `[[tool.uv.index]] pytorch-cpu` block and `[tool.uv.sources] torch = [{ index = "pytorch-cpu", … }]`. Moving `torch` into an extra does **not** change its index pin; the CUDA-free guarantee (`grep -E '^name = "(nvidia|cuda|triton)' uv.lock` → zero matches) must still hold after `uv lock`.

**uv semantics relied on (verify in implementation):**
- `uv sync` does **not** install optional-dependencies unless `--extra <name>`/`--all-extras` is passed. So the shared `deps` stage and `pipeline-api` build become torch-free automatically.
- `uv sync --package pipeline --extra local` resolves the workspace member extra references `embedding[local]` / `labeling[local]`. Implementation must confirm uv expands these transitively; fallback if not: list the leaf libs directly in `pipeline`'s `local` extra.
- After editing any `pyproject.toml`, run `uv lock` and verify `--frozen` installs still succeed.

### 5.2 Import-graph invariant

In API mode the entire pipeline import graph must avoid the local libs. This already holds and must be preserved:
- `embedding/pipeline.py` imports `get_embedder` **lazily** inside `_encode_local` only; top-level imports are `numpy`/`core`/`sqlalchemy`.
- `labeling/llm.py` imports `llama_cpp` lazily inside `_load_llama_class()` and `huggingface_hub` inside `_resolve_model_path()`; top-level imports are stdlib + `core`/`llm`/local prompt/schema modules.

A regression test asserts that importing the pipeline entrypoint with providers=api leaves `torch`, `sentence_transformers`, `llama_cpp`, `huggingface_hub` absent from `sys.modules`.

### 5.3 Runtime guard (fail-fast)

If the slim image is run with a `local` provider, the lazy import must fail with an actionable message rather than a raw `ModuleNotFoundError`.

- `embedding`: wrap the lazy import so a missing `sentence_transformers`/`torch` raises
  `RuntimeError("embedding provider=local but local extra not installed — deploy pipeline-local or set EMBEDDING_PROVIDER=api")`. Mirrors the existing labeling pattern (`"llama-cpp-python is not installed for the labeling package"`).
- `pipeline serve` startup pre-flight: if `embedding_provider == "local"` or `labeling_provider == "local"`, attempt the corresponding import once at boot and fail fast with the same actionable message, so a misconfigured image dies at startup, not mid-cycle.

### 5.4 Dockerfile — stage map (after)

One Dockerfile, BuildKit, layer-cache rules per `docs/docker-sop.md` §Layer-cache rules.

| Stage | Sync command | Contains torch/llama-cpp? |
|---|---|---|
| `base` | — | no |
| `deps` | `uv sync --no-install-workspace --no-dev --frozen` | **no** (extras excluded by default) |
| `api-build` → `api` / `api-dev` | `uv sync --package api …` | no (unchanged) |
| `pipeline-api-build` → `pipeline-api` / `pipeline-api-dev` | `uv sync --package pipeline --no-dev --frozen` | **no** |
| `pipeline-local-build` → `pipeline-local` / `pipeline-local-dev` | `uv sync --package pipeline --extra local --no-dev --frozen` | yes |

- Both pipeline variants install Playwright Chromium + its apt libs (fallback scraper).
- `pipeline-api` bakes `ENV EMBEDDING_PROVIDER=api LABELING_PROVIDER=api`. `pipeline-local` bakes `ENV EMBEDDING_PROVIDER=local LABELING_PROVIDER=local` and keeps `HF_HOME=/models` + the OMP/BLAS thread caps.
- Shared runtime ENV (`PYTHONUNBUFFERED=1`, etc.) and the `python -m pipeline.cli` ENTRYPOINT are unchanged across variants.
- Dev variants are venv-only with source bind-mounted (per SOP). `pipeline-api-dev` is the default dev daemon; `pipeline-local-dev` is for exercising the local path on a workstation.
- `docker-compose.yml` (dev) currently points its `api`/`pipeline-daemon`/`pipeline` services at `target: pipeline-dev` (and `api-dev`). The split retires `pipeline-dev`; update those dev service `target:` refs to `pipeline-api-dev` (default) so dev keeps working, with `pipeline-local-dev` available for local-path work.

### 5.5 Config & defaults

`core/config.py`: `embedding_provider` and `labeling_provider` default → `"api"`. All other knobs unchanged.

`.env.example`: set `EMBEDDING_PROVIDER=api` and `LABELING_PROVIDER=api` as the documented primary path; keep a commented `# =local` block describing the `pipeline-local` image requirement. Analyst already defaults to API (`openai`).

Per-image baked ENV (5.4) is authoritative for each deployed container; `.env` overrides remain possible for operators.

### 5.6 Deploy topology — `docker-compose.prod.yml` (repurposed, 2 GB)

- **No `postgres` service.** `DATABASE_URL` points to an external/managed Postgres (`${DATABASE_URL:?…}`). Bundled Postgres for local work stays only in dev `docker-compose.yml`.
- `api`: `target: api`, `mem_limit: 512m` (starting budget — verify with `docker stats`), `127.0.0.1:8000:8000`, healthcheck per SOP, `restart: always`, json-file log rotation.
- `pipeline-daemon`: `target: pipeline-api`, `command: ["serve"]`, `mem_limit: ~1g` (verify), `EMBEDDING_PROVIDER=api`/`LABELING_PROVIDER=api` (redundant with image ENV, explicit for clarity), required API keys via `${…:?}`, `restart: always`, healthcheck (`pgrep -f 'pipeline.cli serve'`).
- Manual one-shot `pipeline` service (profile `manual`): `target: pipeline-api` (reembed/cluster/score all run on the API path or pure-numpy/UMAP — no torch needed).
- Memory limits use `mem_limit:` (works under `docker compose up` on a single host) rather than `deploy.resources` (Swarm-only). The implementation will reconcile the current file's `deploy.resources` usage to `mem_limit`.

`mem_limit` starting budget (2 GB box, Postgres off-box) — to be confirmed against `docker stats` in the runbook:

| Service | Limit | Notes |
|---|---|---|
| `api` | 512m | FastAPI, no ML |
| `pipeline-daemon` | 1g | ingest + Chromium spikes + UMAP/HDBSCAN; torch/Gemma never loaded |
| (OS headroom) | ~0.5g | — |

### 5.7 Dead-code cleanup

Delete from `labeling/llm.py`: `generate_label_and_insight`, `extract_article_claims`, `deduplicate_claims` (and any now-unused helpers/prompts/`_chat` paths they alone use), plus their tests in `packages/labeling/tests/test_llm.py`. Keep `get_llm`, `_chat`, `_label_local`, `_cluster_insight_local` — they back the still-supported `generate_label`/`generate_cluster_insight` local paths used by `pipeline-local`. `analysis.py` is already a no-op stub; leave it.

### 5.8 Docs to update (same change)

- `docs/docker-sop.md`: Multi-stage targets table (add the `pipeline-api*`/`pipeline-local*` triples, retire the single `pipeline-build`/`pipeline` rows), Image-size budgets (api ≤250MB unchanged; **`pipeline-api` ≤ ~1.2GB**; `pipeline-local` ≤6GB), §Prod compose conventions (Postgres off-box, new `mem_limit`s), and a new rule documenting the `[local]` extra contract.
- `CLAUDE.md`: update the `embedding`/`labeling` rows and the §Pipeline runtime / Quickstart notes to state API-first defaults and the two pipeline image variants.
- `docs/operations-sop.md`: add the **API ⇄ local switch runbook** (§9 below), extending the existing SP3 reembed runbook.
- `.env.example`: per 5.5.

## 6. Reversibility runbook (operations)

**API → local** (need on-box inference again):
1. Build/deploy the `pipeline-local` image (`target: pipeline-local`), mount the `hfcache` volume at `/models`.
2. Set `EMBEDDING_PROVIDER=local` + `LABELING_PROVIDER=local` (image already bakes these).
3. If the local embedding model differs from the rows in DB, run the gated `pipeline reembed` then `pipeline cluster` (per SP3 runbook).
4. Restart the daemon.

**local → API** (the 2 GB default):
1. Set `EMBEDDING_API_KEY` / `LABELING_LLM_API_KEY` (OpenRouter) in prod `.env`.
2. Run `backend/scripts/validate_embeddings.py`; confirm `returned_dims==768` + cluster-quality signals; human go/no-go.
3. **Stop the daemon** (mandatory — the lock does not block reactive embed).
4. Set providers to `api`, run `pipeline reembed` then `pipeline cluster`.
5. Deploy the slim `pipeline-api` image.

## 7. Testing strategy

- **Unit:** extend the existing provider-switch tests (`assert_not_called` on local encoders/LLM when provider=api). Add the import-graph invariant test (5.2). Add a guard test: provider=local with the local extra absent raises the actionable `RuntimeError`.
- **Resolution:** `uv lock` succeeds; `uv sync --package pipeline` (no extra) installs no torch; `uv sync --package pipeline --extra local` installs torch+llama-cpp. CUDA-free grep on `uv.lock` returns zero.
- **Build verification (per SOP §AI reviewers):** build `pipeline-api` and `pipeline-local`; in `pipeline-api` confirm `python -c "import importlib.util,sys; assert importlib.util.find_spec('torch') is None"` and that importing the pipeline entrypoint leaves the four libs out of `sys.modules`; check image sizes against the budget table; verify second-build layer-cache hits.
- **Known pre-existing failure:** `pipeline test_e2e.py::test_e2e_pipeline_and_api` (`/clusters/morning` empty) is unrelated to this work (documented in the migration memory) — out of scope, do not block on it.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| uv does not expand `embedding[local]` transitively through the workspace | Fallback: list leaf libs (`torch`, `sentence-transformers`, `llama-cpp-python`, `huggingface-hub`) directly in `pipeline`'s `local` extra. Verified early in implementation. |
| Slim image accidentally run in local mode → confusing crash | Fail-fast guard (5.3) + baked per-image ENV (5.4). |
| `mem_limit` too low → OOMKilled (Chromium/UMAP spikes) | Budgets are starting points; runbook step verifies with `docker stats` under real load before locking values. |
| Repurposing `docker-compose.prod.yml` breaks an existing bundled-PG deploy | Bundled Postgres remains in dev compose; if a big-box prod is still needed later, add a separate file then. Called out in D3. |
| CUDA wheels reappear after `uv lock` | SOP grep check enforced in test/CI step. |

## 9. Out of scope / deferred

- Removing or sandboxing Playwright/Chromium for additional RAM savings.
- Multi-replica pipeline (singleton assumption unchanged — D24).
- The pre-existing `/clusters/morning` e2e failure.
