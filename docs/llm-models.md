# LLM & Model Inventory

Which models this project runs, for what, and whether they are hosted **API**
calls or **local** on-box weights. Vendor switching for the API LLM is covered
in §"Switching the API vendor".

## API models — `analyst` package (hosted LLM)

The Editorial AI Analyst is the only code that calls a hosted LLM over HTTP.

| Task | Purpose | Default model | Env var |
| --- | --- | --- | --- |
| `analyze` | Extract article attributes + editorial feedback | `gpt-4o` | `ANALYST_ANALYZE_MODEL` |
| `recommend` | Extract data filters, then generate insights (two LLM calls) | `gpt-4o` | `ANALYST_RECOMMEND_MODEL` |

- Client: `openai` SDK, behind the vendor boundary in `analyst/providers.py`.
- Structured output: the schema is injected into the prompt and, when the
  preset's `supports_json_mode` flag is set (the default for all current
  presets), `response_format={"type":"json_object"}` is also sent; output is
  validated against a Pydantic schema with one retry.

### Switching the API vendor

Switching among OpenAI-compatible vendors is a `.env` change only:

1. Set `ANALYST_LLM_PROVIDER` to a preset name.
2. Set `ANALYST_LLM_API_KEY`.
3. Set the model ids to the vendor's format (OpenRouter uses `vendor/model`).
4. For self-hosted endpoints, set `ANALYST_LLM_BASE_URL` to override the host:port.

Preset table (`analyst/providers.py`):

| Provider | Base URL | Notes |
| --- | --- | --- |
| `openai` | `https://api.openai.com/v1` | Default |
| `openrouter` | `https://openrouter.ai/api/v1` | Optional `HTTP-Referer`/`X-Title` via `ANALYST_ATTRIBUTION_*` |
| `ollama` | `http://localhost:11434/v1` | Self-hosted; override base URL for non-local host |
| `vllm` | `http://localhost:8000/v1` | Self-hosted; override base URL for non-local host |

A future native-incompatible vendor (e.g. Anthropic Messages API) is added by
implementing a new `LLMClient` in `analyst/providers.py` plus a preset entry —
no change to `llm.py` or the callers.

## Local models — on-box weights (not vendor-swappable)

| Purpose | Model | Format | Library | Device | Driven by |
| --- | --- | --- | --- | --- | --- |
| Article embedding (768d) | `google/embeddinggemma-300m` | HuggingFace | `sentence-transformers` + `torch` (CPU) | CPU | `EMBEDDING_MODEL_NAME` |
| Cluster labeling | `bartowski/gemma-2-2b-it-GGUF` (`Q4_K_M`) *(default `local`)* or any API preset model | GGUF 4-bit (local) / HTTP (API) | `llama-cpp-python` (local) / shared `llm` package (API) | CPU (local) / remote (API) | `LABELING_PROVIDER` (default `local`); `LABELING_MODEL` for API path |

- The embedding dimension is fixed at `vector(768)`; swapping the embedding
  model requires a DB migration plus a full re-embed (see `decisions.md` D4).
- **Labeling backend is switchable (SP2):** set `LABELING_PROVIDER=local` (default) to run
  on-box Gemma 2B via `llama-cpp-python`; set it to a preset name (`openai`,
  `openrouter`, `ollama`, `vllm`) to route labeling through the shared `llm`
  package with structured JSON output — no Gemma weights loaded. The API path
  uses `LABELING_MODEL`, `LABELING_LLM_API_KEY`, and `LABELING_LLM_BASE_URL`.
- **Note:** On the `local` path the model id remains hardcoded in
  `backend/packages/labeling/src/labeling/llm.py`; the `LLM_MODEL_NAME` env var
  is documented but not read on that path. Known inconsistency, out of scope.

## ML (non-LLM)

| Purpose | Package | Libraries |
| --- | --- | --- |
| Dimensionality reduction → clustering | `clustering` | `umap-learn` → `hdbscan` |
| Scoring (velocity, novelty, coverage) | `scoring` | `scikit-learn`, `numpy` |

## Env var reference

**API (analyst):** `ANALYST_LLM_PROVIDER`, `ANALYST_LLM_API_KEY`,
`ANALYST_LLM_BASE_URL` (optional override), `ANALYST_ANALYZE_MODEL`,
`ANALYST_RECOMMEND_MODEL`, `ANALYST_ATTRIBUTION_REFERER`,
`ANALYST_ATTRIBUTION_TITLE`, `ANALYST_REQUEST_TIMEOUT_SECONDS`.

**Local models:** `EMBEDDING_MODEL_NAME`, `EMBEDDING_MODEL_VERSION`,
`LLM_MODEL_NAME` (documented; see warning above), `LLM_MODEL_VERSION`,
`HF_HOME`, `HF_TOKEN`.

**Labeling backend (SP2):** `LABELING_PROVIDER` (default `local`),
`LABELING_MODEL`, `LABELING_LLM_API_KEY`, `LABELING_LLM_BASE_URL` (optional),
`LABELING_ATTRIBUTION_REFERER`, `LABELING_ATTRIBUTION_TITLE`.
