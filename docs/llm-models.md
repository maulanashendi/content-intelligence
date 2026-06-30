# LLM & Model Inventory

Which models this project runs, for what, and how to switch vendors.

**Hosted API is the default for all three AI tasks** — embedding, cluster
labeling, and the editorial analyst — through an OpenAI-compatible endpoint
reached via the shared `llm` package. This keeps the production footprint inside
a ~2 GB VPS: no `torch`, no GGUF weights, no GPU. On-box weights are an **opt-in
build** (the `pipeline-local` image); see §"Local on-box path".

## AI tasks (hosted by default)

| Task | API default model | Provider env | Notes |
| --- | --- | --- | --- |
| Article embedding (768d) | `openai/text-embedding-3-large` @ 768 via OpenRouter | `EMBEDDING_PROVIDER=api` | `dimensions=768` preserves `vector(768)`; `EMBEDDING_API_{BASE_URL,MODEL,KEY,DIMENSIONS}` |
| Cluster labeling + desk/user-need | `openai/gpt-4o-mini` via OpenRouter | `LABELING_PROVIDER=api` | `LABELING_MODEL`, `LABELING_LLM_{API_KEY,BASE_URL}` |
| Analyst `analyze` | `gpt-4o` (OpenAI) | `ANALYST_LLM_PROVIDER=openai` | `ANALYST_ANALYZE_MODEL` |
| Analyst `recommend` | `gpt-4o` (OpenAI, two LLM calls) | `ANALYST_LLM_PROVIDER=openai` | `ANALYST_RECOMMEND_MODEL` |

- Client: `openai` SDK, behind the provider boundary in the shared `llm` package
  (`llm/providers.py`), reused by `embedding`, `labeling`, and `analyst`.
- Structured output: the schema is injected into the prompt and, when the
  preset's `supports_json_mode` flag is set (default for all current presets),
  `response_format={"type":"json_object"}` is also sent; output is validated
  against a Pydantic schema with one retry.

### Switching the API vendor

Switching among OpenAI-compatible vendors is a `.env` change only. Each task has
its own provider/model env vars (above). To repoint one task: set its
`*_PROVIDER` to a preset name, set its API key, set the model id to the vendor's
format (OpenRouter uses `vendor/model`), and for self-hosted endpoints override
the base URL.

Preset table (`llm/providers.py`):

| Provider | Base URL | Notes |
| --- | --- | --- |
| `openai` | `https://api.openai.com/v1` | Analyst default |
| `openrouter` | `https://openrouter.ai/api/v1` | Embedding + labeling default; optional `HTTP-Referer`/`X-Title` via `*_ATTRIBUTION_*` |
| `ollama` | `http://localhost:11434/v1` | Self-hosted; override base URL for non-local host |
| `vllm` | `http://localhost:8000/v1` | Self-hosted; override base URL for non-local host |

A future native-incompatible vendor (e.g. Anthropic Messages API) is added by
implementing a new `LLMClient` in `llm/providers.py` plus a preset entry — no
change to the callers.

## Local on-box path (opt-in)

Set `EMBEDDING_PROVIDER=local` and/or `LABELING_PROVIDER=local` to run weights
on-box. This requires the heavier `pipeline-local` image (the default
`pipeline-api` image ships without torch/llama-cpp). The path still exists and
is reversible — useful only where a GPU/large box is available.

| Purpose | Local model | Format | Library |
| --- | --- | --- | --- |
| Article embedding (768d) | `google/embeddinggemma-300m` | HuggingFace | `sentence-transformers` + `torch` (CPU) |
| Cluster labeling | `bartowski/gemma-2-2b-it-GGUF` (`Q4_K_M`) | GGUF 4-bit | `llama-cpp-python` (CPU) |

- `vector(768)` is fixed; swapping the embedding model requires a DB migration
  plus a full re-embed (see `decisions.md` D4).
- **Known inconsistency:** on the `local` labeling path the model id is hardcoded
  in `labeling/src/labeling/llm.py`; the `LLM_MODEL_NAME` env var is documented
  but not read on that path. Out of scope.

### Re-embed when switching `EMBEDDING_PROVIDER`

On an existing DB, validate before committing to new vectors (non-destructive;
human go/no-go). Full runbook in `operations-sop.md` §Switching inference backend.

```text
1. Validate (non-destructive, human go/no-go):
   cd backend && ./.venv/bin/python scripts/validate_embeddings.py
2. Cutover (operator-gated; daemon stopped):
   docker compose --profile manual run --rm pipeline reembed
   docker compose --profile manual run --rm pipeline cluster
```

## ML (non-LLM, always on-box)

| Purpose | Package | Libraries |
| --- | --- | --- |
| Dimensionality reduction → clustering | `clustering` | `umap-learn` → `hdbscan` |
| Demand × performance scoring (D35) | `scoring` | `scikit-learn`, `numpy` |

## Env var reference

**Embedding:** `EMBEDDING_PROVIDER` (default `api`), `EMBEDDING_API_BASE_URL`,
`EMBEDDING_API_MODEL`, `EMBEDDING_API_KEY`, `EMBEDDING_API_DIMENSIONS`.
Local-only: `EMBEDDING_MODEL_NAME`, `EMBEDDING_MODEL_VERSION`, `HF_HOME`, `HF_TOKEN`.

**Labeling:** `LABELING_PROVIDER` (default `api`), `LABELING_MODEL`,
`LABELING_LLM_API_KEY`, `LABELING_LLM_BASE_URL` (optional),
`LABELING_ATTRIBUTION_REFERER`, `LABELING_ATTRIBUTION_TITLE`.
Local-only: `LLM_MODEL_NAME` (documented; see warning above), `LLM_MODEL_VERSION`.

**Analyst:** `ANALYST_LLM_PROVIDER` (default `openai`), `ANALYST_LLM_API_KEY`,
`ANALYST_LLM_BASE_URL` (optional override), `ANALYST_ANALYZE_MODEL`,
`ANALYST_RECOMMEND_MODEL`, `ANALYST_ATTRIBUTION_REFERER`,
`ANALYST_ATTRIBUTION_TITLE`, `ANALYST_REQUEST_TIMEOUT_SECONDS`.
