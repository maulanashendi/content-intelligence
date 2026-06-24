# Labeling → API provider (SP2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make cluster labeling backend-switchable — `LABELING_PROVIDER=local` keeps Gemma 2B (unchanged), any `llm` preset name (`openrouter`/`openai`/…) routes the two per-cluster calls through the shared `llm` package via structured JSON output — so on a 2 GB VPS Gemma/`llama-cpp` is never loaded.

**Architecture:** `labeling/llm.py`'s `generate_cluster_insight`/`generate_label` become thin dispatchers: `local` → existing Gemma path (renamed `_*_local`); preset → `_*_api` using `llm.providers.build_client` + `llm.structured.complete_structured` with Pydantic schemas. Both paths return the same dict/str shape, so `labeling/pipeline.py` is untouched. Config lives in `core/config.py`; default `local` keeps behavior identical.

**Tech Stack:** Python 3.11+, uv workspace, shared `llm` package (SP1), `pydantic>=2`, pytest (`asyncio_mode=auto`).

**Reference spec:** `docs/superpowers/specs/2026-06-24-labeling-api-provider-design.md`

## Global Constraints

- `LABELING_PROVIDER` default is `"local"` — behavior is byte-identical until the operator flips it. The value is either `"local"` (Gemma) or an `llm` preset name (`openai`/`openrouter`/`ollama`/`vllm`).
- API path uses `llm.structured.complete_structured` with a Pydantic schema (no regex). The Gemma `local` path keeps its existing `_parse_cluster_insight` regex unchanged.
- Lazy import preserved: the API path must NOT call `get_llm()` / import `llama_cpp`. Keep `llama-cpp-python` as a labeling dependency (one image).
- Labeling LLM config lives in `core/config.py` (single `Settings`), next to `labeling_max_clusters`.
- No new external deps; `labeling` gains a workspace dep on `llm`. Regenerate `uv.lock`; Docker builds use `--frozen`.
- After any `uv sync --package <x>`, restore the dev/test venv with `uv sync --all-packages` (a package sync prunes pytest + other members).
- No comments explaining WHAT; only non-obvious WHY.
- Run tests from `backend/` with `./.venv/bin/python -m pytest`. Run `labeling` and `llm` suites in SEPARATE invocations (each package owns a `tests/conftest.py`).
- Commit: Conventional Commits + trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- No behavior change to `labeling/pipeline.py` (its broad `except Exception` already covers API failures) and no API endpoint change.

---

### Task 1: Config knobs, schemas, API prompts, and the `llm` dependency

Additive foundation — no dispatch logic yet, so behavior is unchanged.

**Files:**
- Modify: `backend/packages/core/src/core/config.py`
- Create: `backend/packages/labeling/src/labeling/schemas.py`
- Modify: `backend/packages/labeling/src/labeling/prompts.py`
- Modify: `backend/packages/labeling/pyproject.toml`
- Modify: `backend/uv.lock` (regenerate)
- Test: `backend/packages/labeling/tests/test_schemas.py` (new), `backend/packages/labeling/tests/test_prompts.py` (extend), `backend/packages/labeling/tests/test_config_labeling.py` (new)

**Interfaces:**
- Produces:
  - `core.config.settings.labeling_provider: str = "local"`, `.labeling_model: str`, `.labeling_llm_api_key: str`, `.labeling_llm_base_url: str`, `.labeling_request_timeout_seconds: float`, `.labeling_attribution_referer: str`, `.labeling_attribution_title: str`
  - `labeling.schemas.ClusterInsightLLM` (fields `label: str`, `what_happened: str|None`, `parties_involved: list[str]|None`, `editorial_angle: str|None`, `summary: list[str]|None`), `labeling.schemas.ClusterLabelLLM` (`label: str`)
  - `labeling.prompts.format_cluster_insight_messages_api(reps) -> list[dict]`, `labeling.prompts.format_label_messages_api(articles) -> list[dict]`

- [ ] **Step 1: Add labeling LLM config**

In `backend/packages/core/src/core/config.py`, immediately after the `labeling_max_clusters: int = 100` line (line 66), add:

```python
    # Labeling backend (SP2): "local" = Gemma; an llm preset name routes to API.
    labeling_provider: str = "local"
    labeling_model: str = "openai/gpt-4o-mini"
    labeling_llm_api_key: str = ""
    labeling_llm_base_url: str = ""
    labeling_request_timeout_seconds: float = 60.0
    labeling_attribution_referer: str = ""
    labeling_attribution_title: str = ""
```

- [ ] **Step 2: Write the config defaults test**

Create `backend/packages/labeling/tests/test_config_labeling.py`:

```python
from core.config import Settings


def test_labeling_defaults() -> None:
    s = Settings(_env_file=None, database_url="postgresql+asyncpg://x:y@localhost/z")
    assert s.labeling_provider == "local"
    assert s.labeling_model == "openai/gpt-4o-mini"
    assert s.labeling_llm_api_key == ""
    assert s.labeling_request_timeout_seconds == 60.0
```

- [ ] **Step 3: Run it (red→green for config)**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_config_labeling.py -v`
Expected: PASS (the fields exist from Step 1).

- [ ] **Step 4: Create the schemas**

Create `backend/packages/labeling/src/labeling/schemas.py`:

```python
from pydantic import BaseModel


class ClusterInsightLLM(BaseModel):
    label: str
    what_happened: str | None = None
    parties_involved: list[str] | None = None
    editorial_angle: str | None = None
    summary: list[str] | None = None


class ClusterLabelLLM(BaseModel):
    label: str
```

- [ ] **Step 5: Write the schema test**

Create `backend/packages/labeling/tests/test_schemas.py`:

```python
from labeling.schemas import ClusterInsightLLM, ClusterLabelLLM


def test_cluster_insight_parses_full_payload() -> None:
    m = ClusterInsightLLM.model_validate(
        {
            "label": "Kenaikan harga beras premium",
            "what_happened": "Harga beras melonjak di sejumlah daerah.",
            "parties_involved": ["Bulog", "Kemendag"],
            "editorial_angle": "Telusuri rantai distribusi.",
            "summary": ["Harga naik 10 persen", "Stok menipis"],
        }
    )
    d = m.model_dump()
    assert d["label"] == "Kenaikan harga beras premium"
    assert d["parties_involved"] == ["Bulog", "Kemendag"]
    assert set(d) == {"label", "what_happened", "parties_involved", "editorial_angle", "summary"}


def test_cluster_insight_minimal() -> None:
    m = ClusterInsightLLM.model_validate({"label": "X"})
    assert m.model_dump() == {
        "label": "X",
        "what_happened": None,
        "parties_involved": None,
        "editorial_angle": None,
        "summary": None,
    }


def test_cluster_label() -> None:
    assert ClusterLabelLLM.model_validate({"label": "Topik singkat"}).label == "Topik singkat"
```

- [ ] **Step 6: Run the schema test**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 7: Add the API prompt builders**

In `backend/packages/labeling/src/labeling/prompts.py`, append:

```python
_CLUSTER_INSIGHT_USER_API = (
    "{system_prompt}\n\n"
    "Berikut {count} sudut liputan berbeda dari satu klaster berita yang sama:\n\n"
    "{articles}\n\n"
    "Hasilkan ringkasan editorial: label topik 5 sampai 7 kata tanpa tanda baca, "
    "apa yang terjadi dalam 1 sampai 2 kalimat, daftar pihak atau tokoh utama, "
    "satu kalimat sudut editorial untuk redaksi, dan beberapa klaim fakta penting."
)

_LABEL_USER_API = (
    "{system_prompt}\n\n"
    "Berikut {count} artikel paling relevan dalam satu klaster:\n\n"
    "{articles}\n\n"
    "Hasilkan satu label topik singkat 5 sampai 7 kata tanpa tanda baca."
)


def format_cluster_insight_messages_api(reps: list[dict]) -> list[dict[str, str]]:
    entries: list[str] = []
    for idx, rep in enumerate(reps, start=1):
        para = ((rep.get("first_paragraph") or "")[:FIRST_PARA_MAX_CHARS]).strip() or "-"
        entries.append(
            f"[Sudut {idx}] Judul: {(rep.get('title') or '').strip()}\nParagraf awal: {para}"
        )
    return [
        {
            "role": "user",
            "content": _CLUSTER_INSIGHT_USER_API.format(
                system_prompt=_CLUSTER_INSIGHT_SYSTEM,
                count=len(reps),
                articles="\n\n".join(entries),
            ),
        }
    ]


def format_label_messages_api(articles: list[dict[str, str | None]]) -> list[dict[str, str]]:
    entries: list[str] = []
    for idx, article in enumerate(articles, start=1):
        entries.append(
            ARTICLE_ENTRY.format(
                idx=idx,
                title=(article.get("title") or "").strip(),
                first_paragraph=(article.get("first_paragraph") or "").strip() or "-",
            )
        )
    return [
        {
            "role": "user",
            "content": _LABEL_USER_API.format(
                system_prompt=SYSTEM_PROMPT,
                count=len(articles),
                articles="\n\n".join(entries),
            ),
        }
    ]
```

- [ ] **Step 8: Extend the prompts test**

Append to `backend/packages/labeling/tests/test_prompts.py`:

```python
from labeling.prompts import format_cluster_insight_messages_api, format_label_messages_api


def test_cluster_insight_api_message_has_article_context() -> None:
    msgs = format_cluster_insight_messages_api(
        [{"title": "Harga beras naik", "first_paragraph": "Melonjak tajam di pasar."}]
    )
    assert len(msgs) == 1 and msgs[0]["role"] == "user"
    body = msgs[0]["content"]
    assert "Harga beras naik" in body
    assert "LABEL:" not in body  # JSON schema is injected by complete_structured, not a prefix format


def test_label_api_message_has_article_context() -> None:
    msgs = format_label_messages_api([{"title": "Topik X", "first_paragraph": "Isi."}])
    assert "Topik X" in msgs[0]["content"]
    assert "LABEL:" not in msgs[0]["content"]
```

- [ ] **Step 9: Run the prompts test**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_prompts.py -v`
Expected: PASS (existing + 2 new).

- [ ] **Step 10: Add the `llm` dependency to labeling**

In `backend/packages/labeling/pyproject.toml`:
- Add `"llm",` to `[project].dependencies` (after `"core",`).
- Add `llm = { workspace = true }` to `[tool.uv.sources]` (after `core = { workspace = true }`).

- [ ] **Step 11: Lock and sync**

Run from `backend/`:
```bash
uv lock
uv sync --all-packages
```
Expected: `uv lock` adds the `labeling → llm` edge (no new external deps). `uv sync --all-packages` keeps the full dev/test venv.

- [ ] **Step 12: Run the labeling suite (no regressions)**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/ -v`
Expected: PASS (existing tests + the new config/schema/prompt tests). Default `labeling_provider="local"` → no behavior change.

- [ ] **Step 13: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add backend/packages/core/src/core/config.py backend/packages/labeling backend/uv.lock
git commit -m "feat(labeling): add API-provider config, schemas, prompts (no dispatch yet)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Provider dispatcher in `labeling/llm.py`

**Files:**
- Modify: `backend/packages/labeling/src/labeling/llm.py`
- Test: `backend/packages/labeling/tests/test_llm.py` (extend)

**Interfaces:**
- Consumes: `core.config.settings.labeling_*` (Task 1), `labeling.schemas.ClusterInsightLLM`/`ClusterLabelLLM` (Task 1), `labeling.prompts.format_cluster_insight_messages_api`/`format_label_messages_api` (Task 1), `llm.providers.build_client`/`attribution_headers`, `llm.structured.complete_structured`.
- Produces (unchanged public signatures): `generate_cluster_insight(reps) -> dict`, `generate_label(articles) -> str`. Both now dispatch on `settings.labeling_provider`.

- [ ] **Step 1: Write the dispatcher tests**

Append to `backend/packages/labeling/tests/test_llm.py`:

```python
from unittest.mock import AsyncMock

from core.config import settings
from labeling.schemas import ClusterInsightLLM, ClusterLabelLLM


async def test_cluster_insight_routes_to_api(monkeypatch) -> None:
    monkeypatch.setattr(settings, "labeling_provider", "openrouter")
    import labeling.llm as lm
    monkeypatch.setattr(lm, "build_client", lambda *a, **k: "CLIENT")
    captured = {}

    async def fake_cs(client, model, messages, schema):
        captured["client"] = client
        captured["model"] = model
        captured["schema"] = schema
        return ClusterInsightLLM(label="Topik uji", parties_involved=["A"])

    monkeypatch.setattr(lm, "complete_structured", fake_cs)
    out = await lm.generate_cluster_insight([{"title": "t", "first_paragraph": "p"}])
    assert out["label"] == "Topik uji"
    assert out["parties_involved"] == ["A"]
    assert set(out) == {"label", "what_happened", "parties_involved", "editorial_angle", "summary"}
    assert captured["client"] == "CLIENT"
    assert captured["model"] == settings.labeling_model
    assert captured["schema"] is ClusterInsightLLM


async def test_label_routes_to_api(monkeypatch) -> None:
    monkeypatch.setattr(settings, "labeling_provider", "openrouter")
    import labeling.llm as lm
    monkeypatch.setattr(lm, "build_client", lambda *a, **k: "CLIENT")

    async def fake_cs(client, model, messages, schema):
        return ClusterLabelLLM(label="  Label Uji  ")

    monkeypatch.setattr(lm, "complete_structured", fake_cs)
    out = await lm.generate_label([{"title": "t", "first_paragraph": "p"}])
    assert out == "Label Uji"


async def test_cluster_insight_local_uses_gemma(monkeypatch) -> None:
    monkeypatch.setattr(settings, "labeling_provider", "local")
    import labeling.llm as lm
    called = {"build": False}
    monkeypatch.setattr(lm, "build_client", lambda *a, **k: called.__setitem__("build", True))
    llm = _make_mock_llm("LABEL: Topik lokal\nAPA_TERJADI: Sesuatu terjadi")
    monkeypatch.setattr(lm, "get_llm", lambda: llm)
    out = await lm.generate_cluster_insight([{"title": "t", "first_paragraph": "p"}])
    assert out["label"] == "Topik lokal"
    assert called["build"] is False  # API client never built on the local path
```

- [ ] **Step 2: Run the tests (verify they fail)**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_llm.py -k "routes_to_api or local_uses_gemma" -v`
Expected: FAIL — `build_client`/`complete_structured` are not yet imported into `labeling.llm`, and dispatch logic does not exist.

- [ ] **Step 3: Refactor `labeling/llm.py` to dispatch**

In `backend/packages/labeling/src/labeling/llm.py`:

(a) Update the imports block at the top to add:
```python
from core.config import settings  # already imported — keep
from llm.providers import attribution_headers, build_client
from llm.structured import complete_structured

from labeling.prompts import (
    format_cluster_insight_messages,
    format_cluster_insight_messages_api,
    format_dedup_messages,
    format_extract_messages,
    format_insight_messages,
    format_label_messages_api,
    format_messages,
)
from labeling.schemas import ClusterInsightLLM, ClusterLabelLLM
```

(b) Rename the existing `async def generate_cluster_insight(reps)` (the Gemma one at ~line 181) to `async def _cluster_insight_local(reps)` — body unchanged.

(c) Rename the existing `async def generate_label(articles)` (the Gemma one at ~line 78) to `async def _label_local(articles)` — body unchanged.

(d) Add the API path + dispatchers:
```python
def _build_labeling_client():
    return build_client(
        settings.labeling_provider,
        settings.labeling_llm_api_key,
        settings.labeling_llm_base_url,
        settings.labeling_request_timeout_seconds,
        attribution_headers(
            settings.labeling_attribution_referer,
            settings.labeling_attribution_title,
        ),
    )


async def _cluster_insight_api(reps: list[dict]) -> dict[str, Any]:
    client = _build_labeling_client()
    result = await complete_structured(
        client,
        settings.labeling_model,
        format_cluster_insight_messages_api(reps),
        ClusterInsightLLM,
    )
    return result.model_dump()


async def _label_api(articles: list[dict[str, str | None]]) -> str:
    client = _build_labeling_client()
    result = await complete_structured(
        client,
        settings.labeling_model,
        format_label_messages_api(articles),
        ClusterLabelLLM,
    )
    return result.label.strip()


async def generate_cluster_insight(reps: list[dict]) -> dict[str, Any]:
    if settings.labeling_provider == "local":
        return await _cluster_insight_local(reps)
    return await _cluster_insight_api(reps)


async def generate_label(articles: list[dict[str, str | None]]) -> str:
    if settings.labeling_provider == "local":
        return await _label_local(articles)
    return await _label_api(articles)
```

Place the dispatchers after the `_*_local` definitions. Do not change `_parse_cluster_insight`, `get_llm`, or any other Gemma helper.

- [ ] **Step 4: Run the dispatcher + existing tests**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_llm.py -v`
Expected: PASS — new api/local dispatch tests pass; existing local-path tests still pass (they patch `get_llm` and run with `labeling_provider` defaulting to `local`).

Note: if any existing local-path test fails because the repo `.env` sets `LABELING_PROVIDER`, add `monkeypatch.setattr(settings, "labeling_provider", "local")` at the top of that test. Do NOT change production defaults.

- [ ] **Step 5: Run the full labeling suite**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add backend/packages/labeling/src/labeling/llm.py backend/packages/labeling/tests/test_llm.py
git commit -m "feat(labeling): dispatch cluster labeling to local Gemma or API by provider

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: De-"analyst"-ify the shared `llm` preset error string

A backlog item from SP1 — `labeling` is now the `llm` package's second consumer, so the error message should be vendor-neutral.

**Files:**
- Modify: `backend/packages/llm/src/llm/providers.py`
- Test: `backend/packages/llm/tests/test_providers.py`

- [ ] **Step 1: Update the test's expected message**

In `backend/packages/llm/tests/test_providers.py`, the unknown-provider tests assert `pytest.raises(ValueError, match="Unknown analyst LLM provider")`. Change both occurrences of the match string to `match="Unknown LLM provider"`.

- [ ] **Step 2: Run it (verify it fails)**

Run: `cd backend && ./.venv/bin/python -m pytest packages/llm/tests/test_providers.py -k unknown -v`
Expected: FAIL — the production message still says "Unknown analyst LLM provider".

- [ ] **Step 3: Update the error string**

In `backend/packages/llm/src/llm/providers.py`, in `get_preset`, change the `ValueError` message from `f"Unknown analyst LLM provider: {provider!r}. ..."` to `f"Unknown LLM provider: {provider!r}. Expected one of {sorted(PRESETS)}"` (drop the word "analyst").

- [ ] **Step 4: Run the llm suite**

Run: `cd backend && ./.venv/bin/python -m pytest packages/llm/tests/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add backend/packages/llm/src/llm/providers.py backend/packages/llm/tests/test_providers.py
git commit -m "refactor(llm): vendor-neutral unknown-provider error message

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Pipeline image wiring, env example, and docs

**Files:**
- Modify: `backend/Dockerfile` (pipeline-build COPY)
- Modify: `backend/.env.example`
- Modify: `docs/llm-models.md`

- [ ] **Step 1: Copy the `llm` source into pipeline-build**

In `backend/Dockerfile`, in the `pipeline-build` stage (the block of `COPY packages/*/src` lines, ~lines 101-107), add:
```dockerfile
COPY packages/llm/src         packages/llm/src
```
Place it next to `COPY packages/core/src` (before `packages/labeling/src`).

- [ ] **Step 2: Document the labeling env knobs**

In `backend/.env.example`, after the Editorial AI Analyst block, add:
```bash
# --- Cluster labeling backend (SP2) ---
# "local" = on-box Gemma 2B (llama-cpp). A preset name routes labeling to an API
# (no Gemma loaded — needed for low-RAM hosts). Presets: openai | openrouter | ollama | vllm
LABELING_PROVIDER=local
LABELING_MODEL=openai/gpt-4o-mini
LABELING_LLM_API_KEY=
LABELING_LLM_BASE_URL=
LABELING_ATTRIBUTION_REFERER=
LABELING_ATTRIBUTION_TITLE=
```

- [ ] **Step 3: Update the model inventory doc**

In `docs/llm-models.md`, in the Local models section's labeling row (or its note), record that labeling is now switchable: `local` Gemma 2B or an API preset via `LABELING_PROVIDER` (structured JSON output through the shared `llm` package; default `local`). Keep the existing hardcoded-model warning for the `local` path.

- [ ] **Step 4: Verify pipeline dependency resolution**

Prefer the real build if Docker is available: `cd backend && docker compose build pipeline-daemon` → succeeds.
If Docker is unavailable here, run the host-equivalent and restore the test venv afterward (a package sync prunes pytest):
```bash
cd backend && uv sync --package pipeline --frozen && uv sync --all-packages
```
Expected: the pipeline env resolves `labeling → llm` with no lockfile error; `uv sync --all-packages` restores the dev/test venv.

- [ ] **Step 5: Sanity re-run + commit**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/ -q` → PASS.
```bash
cd /home/shendi/self-project/content-intelligence
git add backend/Dockerfile backend/.env.example docs/llm-models.md
git commit -m "build(labeling): include llm in pipeline image; document LABELING_PROVIDER

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §2.1 unified `LABELING_PROVIDER` (local | preset) → Task 1 (config) + Task 2 (dispatch) ✓
- §2.2 config in core/config.py → Task 1 Step 1 ✓
- §2.4 structured JSON on API, regex on local → Task 1 (schemas/prompts) + Task 2 (dispatch keeps `_*_local`) ✓
- §2.5 lazy import (api never calls get_llm) → Task 2 dispatch + `test_cluster_insight_local_uses_gemma` asserts `build_client` not called on local; api tests assert `get_llm` not used ✓
- §2.6 get_preset string → Task 3 ✓
- §4.1 schemas → Task 1 Step 4 ✓
- §4.2 config knobs → Task 1 Step 1 ✓
- §4.3 dispatcher → Task 2 ✓
- §4.4 api prompts → Task 1 Step 7 ✓
- §4.6 labeling pyproject `llm` dep + pipeline Dockerfile → Task 1 Step 10 + Task 4 Step 1 ✓
- §7 testing (dispatcher routes, schema, config defaults, no live API) → Tasks 1–2 ✓
- §9 out of scope (analysis.py, embedding, model id env) — untouched ✓

**Placeholder scan:** No TBD/TODO; every code step shows full content.

**Type consistency:** `generate_cluster_insight(reps) -> dict` returns `ClusterInsightLLM().model_dump()` whose keys exactly match the local parser's keys consumed by `pipeline.py` (`label/what_happened/parties_involved/editorial_angle/summary`). `generate_label(articles) -> str`. `complete_structured(client, model, messages, schema)` call shape matches the `llm` package signature. `build_client(provider, api_key, base_url, timeout, headers)` matches the `_build_labeling_client` call. `settings.labeling_model` is the model arg in both api paths and the dispatcher test assertion.
