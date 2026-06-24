# Shared `llm` Package (SP1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the chat-completion LLM provider abstraction out of `analyst` into a new shared workspace package `llm`, so `labeling` (SP2) and `embedding` (SP3) can reuse it — a pure refactor with no behavior change.

**Architecture:** New leaf package `backend/packages/llm` (deps: `openai`, `pydantic`; no `core` dep) holds `providers.py` (presets + client + factory) and `structured.py` (generic JSON structured-output orchestration). `analyst` depends on `llm`, keeps its own `AnalystSettings` and a thin `complete_for_task` glue. Everything moves by `git mv` / verbatim extraction so behavior is identical.

**Tech Stack:** Python 3.11+, uv workspace, `openai>=1.40`, `pydantic>=2`, pytest (`asyncio_mode=auto`).

**Reference spec:** `docs/superpowers/specs/2026-06-24-llm-shared-package-design.md`

## Global Constraints

- New package lives at `backend/packages/llm` with src layout (`src/llm/...`); no flat layout.
- `llm` depends ONLY on `openai>=1.40` and `pydantic>=2` — NOT on `core` (it is a leaf shared library).
- `llm` is config-agnostic: it takes explicit params. App config (`AnalystSettings`) stays in `analyst`.
- Pure refactor: NO behavior change to `analyst`. The only allowed text change is the internal log message string (de-"analyst"-ified) in the moved structured-output helper.
- No new external dependencies beyond `openai`/`pydantic` (already in `uv.lock`); regenerate and commit `uv.lock` in the same change (Docker builds use `--frozen`).
- No comments explaining WHAT; only non-obvious WHY.
- Run tests from `backend/` with `./.venv/bin/python -m pytest`. `analyst` and `api` both define `tests/conftest.py`, so run their suites in SEPARATE pytest invocations (a combined run raises `ImportPathMismatchError`).
- Commit messages: Conventional Commits + trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- No API endpoint changes; `/api/v1/analyst/*` and its API-layer tests (which mock `analyze.run_analysis`/`recommend.run_recommendation`) stay green.

---

### Task 1: Move the chat abstraction into a new `llm` package (atomic move)

This is one atomic refactor committed together: creating `llm` and rewiring `analyst` are two halves of the same move — `analyst` is broken in between, so green is asserted only at the end. No transient duplicated code is committed.

**Files:**
- Create: `backend/packages/llm/pyproject.toml`
- Create: `backend/packages/llm/src/llm/__init__.py`
- Move: `backend/packages/analyst/src/analyst/providers.py` → `backend/packages/llm/src/llm/providers.py` (`git mv`, verbatim)
- Create: `backend/packages/llm/src/llm/structured.py` (extracted from `analyst/src/analyst/llm.py`)
- Create: `backend/packages/llm/tests/conftest.py`
- Move: `backend/packages/analyst/tests/test_providers.py` → `backend/packages/llm/tests/test_providers.py` (`git mv` + import rebase)
- Create: `backend/packages/llm/tests/test_structured.py`
- Modify: `backend/packages/analyst/src/analyst/llm.py` (reduce to `complete_for_task` glue)
- Modify: `backend/packages/analyst/tests/test_llm.py` (replace with wiring test)
- Modify: `backend/packages/analyst/tests/conftest.py` (add `llm/src` to `sys.path`)
- Modify: `backend/packages/analyst/pyproject.toml` (add `llm` dep + source, drop `openai`)
- Modify: `backend/pyproject.toml` (`[tool.uv.sources]` add `llm`)
- Regenerate: `backend/uv.lock`

**Interfaces:**
- Produces (in package `llm`):
  - `llm.providers`: `ProviderPreset`, `PRESETS`, `get_preset`, `resolve_base_url`, `attribution_headers`, `LLMClient` (Protocol), `OpenAICompatibleClient`, `build_client(provider, api_key, base_url_override, timeout, headers) -> OpenAICompatibleClient`
  - `llm.structured`: `complete_structured(client: LLMClient, model, messages, schema: type[T]) -> T`
- Produces (in `analyst`): `analyst.llm.complete_for_task(task, messages, schema) -> T` (unchanged signature)
- Consumers unchanged: `analyst.analyze` / `analyst.recommend` call `llm.complete_for_task` via `from analyst import llm`.

- [ ] **Step 1: Create the `llm` package manifest**

Create `backend/packages/llm/pyproject.toml`:

```toml
[project]
name = "llm"
version = "0.1.0"
description = "Shared LLM client kernel: OpenAI-compatible provider presets + structured output"
requires-python = ">=3.11"
dependencies = [
  "openai>=1.40",
  "pydantic>=2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/llm"]
```

- [ ] **Step 2: Create the package `__init__`**

Create `backend/packages/llm/src/llm/__init__.py` as an empty file.

- [ ] **Step 3: Move `providers.py` verbatim**

```bash
cd /home/shendi/self-project/content-intelligence/backend
mkdir -p packages/llm/src/llm packages/llm/tests
git mv packages/analyst/src/analyst/providers.py packages/llm/src/llm/providers.py
```
Do not edit its contents — it has no `analyst` imports, so it moves clean.

- [ ] **Step 4: Create `structured.py` (extracted from analyst/llm.py)**

Create `backend/packages/llm/src/llm/structured.py`:

```python
import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from llm.providers import LLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
    return text.strip()


def _augment(messages: list[dict[str, str]], schema: type[BaseModel]) -> list[dict[str, str]]:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    suffix = f"\n\nRespond ONLY with a single valid JSON object matching this schema:\n{schema_json}"
    out = [dict(m) for m in messages]
    for m in out:
        if m["role"] == "system":
            m["content"] = m["content"] + suffix
            return out
    out.insert(0, {"role": "system", "content": suffix.strip()})
    return out


async def complete_structured(
    client: LLMClient,
    model: str,
    messages: list[dict[str, str]],
    schema: type[T],
) -> T:
    augmented = _augment(messages, schema)
    last_exc: Exception | None = None
    for attempt in (1, 2):
        raw = await client.complete(model=model, messages=augmented)
        try:
            return schema.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning(
                "llm returned invalid structured output",
                extra={"attempt": attempt, "schema": schema.__name__},
            )
    raise ValueError(f"LLM returned invalid output for {schema.__name__}: {last_exc}")
```

- [ ] **Step 5: Create the `llm` test conftest**

Create `backend/packages/llm/tests/conftest.py`:

```python
import sys
from pathlib import Path

import pytest

llm_src = Path(__file__).parent.parent / "src"
if str(llm_src) not in sys.path:
    sys.path.insert(0, str(llm_src))


@pytest.fixture(scope="session", autouse=True)
def _isolate_test_database() -> None:
    """Override root conftest's database fixture — llm tests don't need a DB."""
    pass


@pytest.fixture(scope="session", autouse=True)
def _assert_test_db_clean_at_session_end() -> None:
    """Override root conftest's database cleanup fixture."""
    yield
```

- [ ] **Step 6: Move the provider tests and rebase their import**

```bash
cd /home/shendi/self-project/content-intelligence/backend
git mv packages/analyst/tests/test_providers.py packages/llm/tests/test_providers.py
```
Then in `packages/llm/tests/test_providers.py`, change every `from analyst.providers import ...` to `from llm.providers import ...` (there is a single consolidated import block at the top after the earlier consolidation). Change nothing else.

- [ ] **Step 7: Create `test_structured.py` (generic, no analyst import)**

Create `backend/packages/llm/tests/test_structured.py`:

```python
import pytest
from pydantic import BaseModel

from llm.structured import complete_structured


class _Out(BaseModel):
    reply: str


class FakeLLMClient:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[dict] = []

    async def complete(self, *, model: str, messages: list[dict]) -> str:
        self.calls.append({"model": model, "messages": messages})
        return self._contents[len(self.calls) - 1]


async def test_parses_valid_json() -> None:
    client = FakeLLMClient(['{"reply":"pong"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], _Out)
    assert result.reply == "pong"


async def test_strips_code_fences() -> None:
    client = FakeLLMClient(['```json\n{"reply":"pong"}\n```'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], _Out)
    assert result.reply == "pong"


async def test_retries_once_then_succeeds() -> None:
    client = FakeLLMClient(["not json", '{"reply":"pong"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], _Out)
    assert result.reply == "pong"
    assert len(client.calls) == 2


async def test_raises_after_two_failures() -> None:
    client = FakeLLMClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        await complete_structured(client, "m", [{"role": "user", "content": "x"}], _Out)
```

- [ ] **Step 8: Reduce `analyst/llm.py` to the glue**

Replace the entire contents of `backend/packages/analyst/src/analyst/llm.py` with:

```python
from typing import TypeVar

from pydantic import BaseModel

from analyst.config import settings
from llm.providers import attribution_headers, build_client
from llm.structured import complete_structured

T = TypeVar("T", bound=BaseModel)


async def complete_for_task(
    task: str, messages: list[dict[str, str]], schema: type[T]
) -> T:
    client = build_client(
        settings.analyst_llm_provider,
        settings.analyst_llm_api_key,
        settings.analyst_llm_base_url,
        settings.analyst_request_timeout_seconds,
        attribution_headers(
            settings.analyst_attribution_referer,
            settings.analyst_attribution_title,
        ),
    )
    return await complete_structured(client, settings.model_for(task), messages, schema)
```

- [ ] **Step 9: Replace `analyst/tests/test_llm.py` with a wiring test**

Replace the entire contents of `backend/packages/analyst/tests/test_llm.py` with:

```python
import analyst.llm as alm
from pydantic import BaseModel


class _Schema(BaseModel):
    x: str


async def test_complete_for_task_wires_settings(monkeypatch) -> None:
    captured: dict = {}

    def fake_build_client(provider, api_key, base_url, timeout, headers):
        captured["provider"] = provider
        return "CLIENT"

    async def fake_complete_structured(client, model, messages, schema):
        captured["client"] = client
        captured["model"] = model
        return _Schema(x="ok")

    monkeypatch.setattr(alm, "build_client", fake_build_client)
    monkeypatch.setattr(alm, "complete_structured", fake_complete_structured)

    out = await alm.complete_for_task("analyze", [{"role": "user", "content": "hi"}], _Schema)

    assert out.x == "ok"
    assert captured["client"] == "CLIENT"
    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-4o"
```

- [ ] **Step 10: Add `llm/src` to the analyst test conftest path**

In `backend/packages/analyst/tests/conftest.py`, after the existing `core_src` path line, add an `llm_src` entry so analyst tests can import the `llm` package. The path block becomes:

```python
analyst_src = Path(__file__).parent.parent / "src"
core_src = Path(__file__).parent.parent.parent / "core" / "src"
llm_src = Path(__file__).parent.parent.parent / "llm" / "src"

for p in (analyst_src, core_src, llm_src):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
```
(Replace the two existing `if str(...) not in sys.path` insert blocks with this loop; keep the imports and fixtures below unchanged.)

- [ ] **Step 11: Update `analyst/pyproject.toml` deps**

In `backend/packages/analyst/pyproject.toml`:
- In `[project].dependencies`, remove the `"openai>=1.40",` line and add `"llm",`.
- In `[tool.uv.sources]`, add `llm = { workspace = true }` (next to the existing `core = { workspace = true }`).

Resulting dependencies list:
```toml
dependencies = [
  "core",
  "llm",
  "pydantic>=2",
  "pydantic-settings>=2",
]
```
```toml
[tool.uv.sources]
core = { workspace = true }
llm = { workspace = true }
```

- [ ] **Step 12: Register `llm` in the root workspace sources**

In `backend/pyproject.toml` `[tool.uv.sources]`, add a line `llm = { workspace = true }` alongside the other workspace members.

- [ ] **Step 13: Regenerate the lockfile and sync the venv**

Run from `backend/`:
```bash
uv lock
uv sync
```
Expected: `uv lock` adds the `llm` workspace member (no new external resolutions — `openai`/`pydantic` already locked). `uv sync` installs `llm` editable into `.venv`.

- [ ] **Step 14: Run the `llm` suite**

Run: `cd backend && ./.venv/bin/python -m pytest packages/llm/tests/ -v`
Expected: PASS (test_providers all pass; test_structured 4 pass).

- [ ] **Step 15: Run the `analyst` suite**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/ -v`
Expected: PASS (test_config unchanged; test_llm wiring test passes; analyze/recommend/category/schemas unchanged).

- [ ] **Step 16: Run the API analyst contract suite**

Run: `cd backend && ./.venv/bin/python -m pytest packages/api/tests/analyst/ -v`
Expected: PASS (3 tests; they mock `run_analysis`/`run_recommendation`, unaffected).

- [ ] **Step 17: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add backend/packages/llm backend/packages/analyst backend/pyproject.toml backend/uv.lock
git commit -m "refactor(llm): extract shared llm package from analyst

Move provider presets/client + structured-output orchestration into a new
leaf package 'llm' (openai+pydantic, no core dep). analyst now depends on llm
and keeps only AnalystSettings + complete_for_task glue. No behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Wire the `llm` package into the Docker build

**Files:**
- Modify: `backend/Dockerfile` (deps stage COPY; api-build COPY; api-dev reload-dir)

**Interfaces:**
- Consumes: the `llm` package created in Task 1 (its `pyproject.toml` and `src/llm`).
- Produces: an `api` image whose venv resolves `analyst → llm` under `uv sync --frozen`.

- [ ] **Step 1: Copy the `llm` manifest in the deps stage**

In `backend/Dockerfile`, in the `deps` stage (the block of `COPY packages/*/pyproject.toml` lines, currently lines ~18-26), add:
```dockerfile
COPY packages/llm/pyproject.toml         packages/llm/pyproject.toml
```
Place it next to the other package manifest COPY lines (e.g., right after the `analyst` line).

- [ ] **Step 2: Copy the `llm` source in the api-build stage**

In the `api-build` stage (currently lines ~31-36), add the `llm` source COPY alongside core/analyst/api:
```dockerfile
COPY packages/llm/src     packages/llm/src
```
Place it before `COPY packages/api/src`.

- [ ] **Step 3: Add `llm` to the api-dev reload dirs**

In the `api-dev` stage `CMD`, add a reload dir for `llm` after the analyst one:
```dockerfile
     "--reload-dir", "/app/packages/llm/src", \
```

- [ ] **Step 4: Build the api image to verify resolution**

Run: `cd backend && docker compose build api`
Expected: build succeeds; the `deps` and `api-build` stages run `uv sync ... --frozen` without lockfile errors (proves `uv.lock` from Task 1 is consistent and `llm` resolves).

If Docker build is not available in this environment, run the equivalent host check instead and say so in the report:
`cd backend && uv sync --package api --frozen` → expected: succeeds, installs `llm`.

- [ ] **Step 5: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add backend/Dockerfile
git commit -m "build(llm): include shared llm package in the api image

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Documentation

No automated test cycle; verify by reading the edited files.

**Files:**
- Modify: `CLAUDE.md` (Modules table + "share via core" rule note)
- Modify: `docs/tech-stack.md` (note the `llm` package)

- [ ] **Step 1: Add the `llm` module row in CLAUDE.md**

In `CLAUDE.md`, in the Modules table (`## Modules (backend/packages/)`), add a row for `llm`. Place it directly above the `analyst` row:
```markdown
| `llm`        | Shared LLM client kernel: provider presets + structured output | openai SDK; imported by `analyst` (and `labeling` in SP2); no `core` dep |
```

- [ ] **Step 2: Update the "share via core" rule note in CLAUDE.md**

In `CLAUDE.md`, find the rule line under `## Modules`:
`Rule: api never imports ML modules. Batch modules never import each other — share via core. Cross-module imports must be declared in pyproject.toml.`
Replace the middle clause so it reads:
`Rule: api never imports ML modules. Batch modules never import each other — share via core (DB kernel) or llm (LLM client kernel). Cross-module imports must be declared in pyproject.toml.`

- [ ] **Step 3: Note the `llm` package in tech-stack.md**

In `docs/tech-stack.md`, on the `openai` dependency row (the line beginning `` | `openai` >=1.40 ``), append to its rightmost cell: ` Lives in the shared `llm` package (provider presets + structured output), reused by analyst and labeling.`

- [ ] **Step 4: Verify**

Confirm `CLAUDE.md` shows the new `llm` row and updated rule, and `docs/tech-stack.md` mentions the `llm` package. Sanity re-run (docs don't touch code): `cd backend && ./.venv/bin/python -m pytest packages/llm/tests/ -q` → PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/shendi/self-project/content-intelligence
git add CLAUDE.md docs/tech-stack.md
git commit -m "docs(llm): document shared llm package + shared-kernel rule

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §4.1 `llm/pyproject.toml` → Task 1 Step 1 ✓
- §4.2 `providers.py` moved verbatim → Task 1 Step 3 ✓
- §4.3 `structured.py` extracted (generic log message) → Task 1 Step 4 ✓
- §4.4 `llm` tests (providers moved + structured + conftest) → Task 1 Steps 5–7 ✓
- §5 analyst rewire (delete providers, slim llm.py, config unchanged, pyproject, tests) → Task 1 Steps 6,8–11 ✓
- §6 workspace + uv.lock + Dockerfile → Task 1 Steps 12–13, Task 2 ✓
- §7 docs (CLAUDE.md rows + rule, tech-stack) → Task 3 ✓
- §8 testing (llm/analyst/api-analyst separately) → Task 1 Steps 14–16 ✓

**Placeholder scan:** No TBD/TODO; every code/edit step shows full content or an exact command.

**Type consistency:** `build_client(provider, api_key, base_url_override, timeout, headers)` (Task 1 Step 3 moved file) matches `analyst.llm.complete_for_task`'s call (Task 1 Step 8) and the wiring test's `fake_build_client(provider, api_key, base_url, timeout, headers)` (Task 1 Step 9). `complete_structured(client, model, messages, schema)` in `structured.py` (Step 4) matches its call in `complete_for_task` (Step 8) and `fake_complete_structured` (Step 9). The wiring test monkeypatches `analyst.llm.build_client`/`analyst.llm.complete_structured`, which exist as module attributes because Step 8 imports them by name into `analyst.llm`.
