# Editorial AI Analyst — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-contained `analyst` backend package and `/api/v1/analyst/*` endpoints that port the standalone Editorial AI Analyst (article scoring + recommendation insights) onto a config-driven, OpenAI-compatible LLM client — without touching content-intelligence's ML pipeline.

**Architecture:** New uv-workspace package `analyst` depends only on `core`. It owns its own LLM client (OpenAI-compatible, `base_url`+`key`+`model`, per-task config) — "local" vs "API" is just a base-URL swap, so the package never imports torch/llama-cpp and never touches the pipeline daemon. The existing `api` package gains one route module that imports `analyst` (HTTP-only, so the "api never imports ML" rule holds). Recommendation is reimplemented directly on the client (no LangChain), reading a static ported dataset.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pydantic-settings, `openai` SDK (against any OpenAI-compatible endpoint), uv workspace, pytest/pytest-asyncio, ruff, Docker.

## Global Constraints

- **src layout** per package; `packages/analyst/src/analyst/...`. No flat layout.
- **`analyst` depends only on `core`.** It must not import `ingest`, `embedding`, `clustering`, `labeling`, `scoring`, or `pipeline`, and none of them import it. Cross-module deps declared in `pyproject.toml`.
- **`api` never imports ML / torch.** `analyst` pulls only the `openai` SDK (httpx-based) — adding it to `api` keeps the image ML-free. Do not add torch/transformers/llama-cpp to `analyst`.
- **No in-process model, no daemon.** The analyst is request/response only. No `pg_notify`, no scheduler, no DB tables.
- **OpenAPI contract:** every endpoint has a Pydantic `response_model=`, explicit status code, and a one-line `summary=`. The contract is `/openapi.json` — no separate markdown.
- **JSON logging only:** use `logging.getLogger(__name__)`. No `print()`.
- **No new top-level dep without updating `docs/tech-stack.md`** — `openai` is new; update it (Task 8).
- **Auth/rate-limiting handled upstream** — do NOT port `slowapi`, bearer auth, CORS, or Mangum/Lambda.
- **Tests run on the host venv:** `cd backend && ./.venv/bin/python -m pytest <path> -v` (not `uv run`). Use `uv sync` / `uv lock` for env management only.
- **ruff** line-length 100, double quotes; rules `E,F,I,N,W,UP,B,SIM` (E501 ignored).
- **Decision log:** add **D37** (Task 8). Latest existing is D36.

**Source files being ported (read-only references, in-repo):**
- `user-need/data-user-need-backend/schemas.py` — Pydantic models (copy verbatim)
- `user-need/data-user-need-backend/services.py` — `SYSTEM_PROMPT` (lines 7–67) + category logic (lines 108–233)
- `user-need/data-user-need-backend/recommendation_service.py` — prompts + `_apply_filters`
- `user-need/data-user-need-backend/airflow_data.json` — the dataset to copy

---

### Task 1: Scaffold the `analyst` package + config

**Files:**
- Create: `backend/packages/analyst/pyproject.toml`
- Create: `backend/packages/analyst/src/analyst/__init__.py`
- Create: `backend/packages/analyst/src/analyst/config.py`
- Create: `backend/packages/analyst/tests/__init__.py`
- Create: `backend/packages/analyst/tests/test_config.py`
- Modify: `backend/pyproject.toml:15-23` (add `analyst` to `[tool.uv.sources]`)
- Modify: `backend/.env.example` (append analyst keys)

**Interfaces:**
- Produces: `analyst.config.settings` — an `AnalystSettings` instance with `.model_for(task)` and `.base_url_for(task)` where `task ∈ {"analyze","recommend"}`.

- [ ] **Step 1: Write the package manifest**

Create `backend/packages/analyst/pyproject.toml`:

```toml
[project]
name = "analyst"
version = "0.1.0"
description = "Editorial AI Analyst — article scoring + recommendation insights over an OpenAI-compatible LLM"
requires-python = ">=3.11"
dependencies = [
  "core",
  "openai>=1.40",
  "pydantic>=2",
  "pydantic-settings>=2",
]

[tool.uv.sources]
core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/analyst"]
```

- [ ] **Step 2: Register the package in the workspace sources**

In `backend/pyproject.toml`, add one line inside the existing `[tool.uv.sources]` block (after `pipeline = { workspace = true }` on line 23):

```toml
analyst = { workspace = true }
```

- [ ] **Step 3: Create the package skeleton**

Create `backend/packages/analyst/src/analyst/__init__.py` (empty file) and `backend/packages/analyst/tests/__init__.py` (empty file).

- [ ] **Step 4: Write the config module**

Create `backend/packages/analyst/src/analyst/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalystSettings(BaseSettings):
    """Config for the Editorial AI Analyst.

    'local' vs 'API' is a base-URL swap: point a task's *_base_url at a local
    OpenAI-compatible server (Ollama/llama.cpp/vLLM) or a hosted endpoint.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    analyst_llm_base_url: str = "https://api.openai.com/v1"
    analyst_llm_api_key: str = ""
    analyst_request_timeout_seconds: float = 60.0

    analyst_analyze_model: str = "gpt-4o"
    analyst_analyze_base_url: str = ""
    analyst_recommend_model: str = "gpt-4o"
    analyst_recommend_base_url: str = ""

    def model_for(self, task: str) -> str:
        return getattr(self, f"analyst_{task}_model")

    def base_url_for(self, task: str) -> str:
        override: str = getattr(self, f"analyst_{task}_base_url")
        return override or self.analyst_llm_base_url


settings = AnalystSettings()
```

- [ ] **Step 5: Write the failing test**

Create `backend/packages/analyst/tests/test_config.py`:

```python
from analyst.config import AnalystSettings


def test_defaults_and_per_task_resolution() -> None:
    s = AnalystSettings(_env_file=None)
    assert s.model_for("analyze") == "gpt-4o"
    assert s.model_for("recommend") == "gpt-4o"
    # falls back to the shared base url when no per-task override is set
    assert s.base_url_for("analyze") == "https://api.openai.com/v1"


def test_per_task_base_url_override() -> None:
    s = AnalystSettings(
        _env_file=None,
        analyst_recommend_base_url="http://localhost:11434/v1",
    )
    assert s.base_url_for("recommend") == "http://localhost:11434/v1"
    assert s.base_url_for("analyze") == "https://api.openai.com/v1"
```

- [ ] **Step 6: Sync the workspace and run the test (expect failure first)**

Run:
```bash
cd backend && uv lock && uv sync
./.venv/bin/python -m pytest packages/analyst/tests/test_config.py -v
```
Expected: PASS (config + manifest are written together; the deliverable is "the package resolves in uv and config works"). If `import analyst` fails, `uv sync` did not install the new package — re-check Steps 1–2.

- [ ] **Step 7: Append env-var docs**

Append to `backend/.env.example`:

```bash
# --- Editorial AI Analyst (D37) ---
# 'local' vs 'API' is a base-URL swap. Hosted default shown; for a local
# server set ANALYST_LLM_BASE_URL=http://localhost:11434/v1 (Ollama) etc.
ANALYST_LLM_BASE_URL=https://api.openai.com/v1
ANALYST_LLM_API_KEY=
ANALYST_ANALYZE_MODEL=gpt-4o
ANALYST_RECOMMEND_MODEL=gpt-4o
```

- [ ] **Step 8: Commit**

```bash
cd backend && git add packages/analyst/pyproject.toml packages/analyst/src packages/analyst/tests pyproject.toml uv.lock .env.example
git commit -m "feat(analyst): scaffold package + per-task LLM config"
```

---

### Task 2: Port the Pydantic schemas

**Files:**
- Create: `backend/packages/analyst/src/analyst/schemas.py`
- Create: `backend/packages/analyst/tests/test_schemas.py`

**Interfaces:**
- Produces: `FeatureData`, `ArticleFeatures` (16 `FeatureData` fields `f01_breaking`…`f16_social_buzz`), `ArticleRequest{title,content}`, `BatchArticleRequest{articles}`, `EditorialFeedback`, `ArticleAnalysisResult{features,feedback}`, `RecommendationRequest{intent,dataset?}`, `DataFilterParameters`, `RecommendationInsight{title,insight,action}`, `RecommendationOutput`, plus NEW `UserNeedScore{category:str,score:float}`, `AnalyzeResult{features:ArticleFeatures,editorial_feedback:EditorialFeedback,user_needs:list[UserNeedScore]}`, `RecommendationInsightsLLM{insights:list[RecommendationInsight],summary:str}`.

- [ ] **Step 1: Copy the ported schema file**

Copy `user-need/data-user-need-backend/schemas.py` verbatim to `backend/packages/analyst/src/analyst/schemas.py`. It imports only `pydantic`, so it is self-contained. Do not modify the existing classes.

- [ ] **Step 2: Append the new response/aggregate models**

Append to `backend/packages/analyst/src/analyst/schemas.py`:

```python
class UserNeedScore(BaseModel):
    category: str
    score: float


class AnalyzeResult(BaseModel):
    """API response for /analyze — the service's full structured output."""

    features: ArticleFeatures
    editorial_feedback: EditorialFeedback
    user_needs: list[UserNeedScore]


class RecommendationInsightsLLM(BaseModel):
    """Stage-2 structured output: the insights + summary the LLM returns."""

    model_config = ConfigDict(extra="forbid")

    insights: list[RecommendationInsight] = Field(default_factory=list)
    summary: str = ""
```

- [ ] **Step 3: Write the failing test**

Create `backend/packages/analyst/tests/test_schemas.py`:

```python
from analyst.schemas import (
    AnalyzeResult,
    ArticleAnalysisResult,
    RecommendationOutput,
    UserNeedScore,
)


def _feature(status: int) -> dict:
    return {"status": status, "reasoning": "x"}


def _all_features(status: int = 0) -> dict:
    return {f"f{n:02d}_x": _feature(status) for n in range(1, 17)}


def test_analysis_result_parses_16_features() -> None:
    payload = {
        "features": {
            k: v
            for k, v in zip(
                [
                    "f01_breaking", "f02_live_developing", "f03_timeless",
                    "f04_explanatory", "f05_data_investigative", "f06_author_voice",
                    "f07_depth_analysis", "f08_expert_quotes", "f09_emotional_positive",
                    "f10_conflict_tragedy", "f11_light_humor", "f12_actionable_steps",
                    "f13_collective_call", "f14_community_identity", "f15_listicle_format",
                    "f16_social_buzz",
                ],
                [_feature(0)] * 16,
            )
        },
        "feedback": {
            "recommendation_judul": ["a"],
            "missing_info": [],
            "bias_check": [],
            "next_angle": [],
        },
    }
    result = ArticleAnalysisResult.model_validate(payload)
    assert result.features.f01_breaking.status == 0


def test_analyze_result_round_trip() -> None:
    res = AnalyzeResult(
        features=ArticleAnalysisResult.model_validate(
            {
                "features": {
                    name: _feature(0)
                    for name in [
                        "f01_breaking", "f02_live_developing", "f03_timeless",
                        "f04_explanatory", "f05_data_investigative", "f06_author_voice",
                        "f07_depth_analysis", "f08_expert_quotes", "f09_emotional_positive",
                        "f10_conflict_tragedy", "f11_light_humor", "f12_actionable_steps",
                        "f13_collective_call", "f14_community_identity", "f15_listicle_format",
                        "f16_social_buzz",
                    ]
                },
                "feedback": {
                    "recommendation_judul": [], "missing_info": [],
                    "bias_check": [], "next_angle": [],
                },
            }
        ).features,
        editorial_feedback=ArticleAnalysisResult.model_validate(
            {
                "features": {
                    name: _feature(0)
                    for name in [
                        "f01_breaking", "f02_live_developing", "f03_timeless",
                        "f04_explanatory", "f05_data_investigative", "f06_author_voice",
                        "f07_depth_analysis", "f08_expert_quotes", "f09_emotional_positive",
                        "f10_conflict_tragedy", "f11_light_humor", "f12_actionable_steps",
                        "f13_collective_call", "f14_community_identity", "f15_listicle_format",
                        "f16_social_buzz",
                    ]
                },
                "feedback": {
                    "recommendation_judul": [], "missing_info": [],
                    "bias_check": [], "next_angle": [],
                },
            }
        ).feedback,
        user_needs=[UserNeedScore(category="Help me", score=100.0)],
    )
    assert res.user_needs[0].category == "Help me"


def test_recommendation_output_defaults() -> None:
    out = RecommendationOutput(filters_applied={}, summary="s")
    assert out.data_source == "mock"
    assert out.insights == []
```

- [ ] **Step 4: Run the test**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd backend && git add packages/analyst/src/analyst/schemas.py packages/analyst/tests/test_schemas.py
git commit -m "feat(analyst): port pydantic schemas + analyze/recommend response models"
```

---

### Task 3: Port the category rule engine (pure Python)

**Files:**
- Create: `backend/packages/analyst/src/analyst/category.py`
- Create: `backend/packages/analyst/tests/test_category.py`

**Interfaces:**
- Consumes: `analyst.schemas.ArticleFeatures`, `analyst.schemas.UserNeedScore`.
- Produces: `rank_user_needs(features: ArticleFeatures) -> list[UserNeedScore]` — the 8 categories sorted by score descending.

- [ ] **Step 1: Write the module**

Create `backend/packages/analyst/src/analyst/category.py`. Copy the `TEMPO_REFERENCE_VECTORS` and `LOGIC_RULES` dicts verbatim from `user-need/data-user-need-backend/services.py` (lines 108–177), then add the function below (a refactor of `calculate_category_logic`, lines 179–233, returning the full sorted list of `UserNeedScore` instead of a top-2 tuple):

```python
from analyst.schemas import ArticleFeatures, UserNeedScore

# --- paste TEMPO_REFERENCE_VECTORS (services.py lines 108-117) here ---
# --- paste LOGIC_RULES (services.py lines 119-177) here ---


def rank_user_needs(features: ArticleFeatures) -> list[UserNeedScore]:
    features_full = features.model_dump()
    features_dict = {key: val["status"] for key, val in features_full.items()}
    vector = list(features_dict.values())

    scores: list[UserNeedScore] = []
    for category, rules in LOGIC_RULES.items():
        ref_vector = TEMPO_REFERENCE_VECTORS[category]
        matches = sum(1 for a, b in zip(vector, ref_vector) if a == b)
        base_score = (matches / 16) * 100

        rejected = False
        for f_key in rules["reject_if_any"]:
            if features_dict.get(f_key) == 1:
                base_score = 0.0
                rejected = True
                break
        if rejected:
            scores.append(UserNeedScore(category=category, score=0.0))
            continue

        if rules["must_have_all"] and any(
            features_dict.get(f_key) == 0 for f_key in rules["must_have_all"]
        ):
            base_score *= 0.3

        if rules["must_have_one_of"] and not any(
            features_dict.get(f_key) == 1 for f_key in rules["must_have_one_of"]
        ):
            base_score *= 0.5

        for f_key in rules["boosters"]:
            if features_dict.get(f_key) == 1:
                base_score += 5

        scores.append(UserNeedScore(category=category, score=min(base_score, 100.0)))

    scores.sort(key=lambda s: s.score, reverse=True)
    return scores
```

- [ ] **Step 2: Write the failing test**

Create `backend/packages/analyst/tests/test_category.py`:

```python
from analyst.category import rank_user_needs
from analyst.schemas import ArticleFeatures

_NAMES = [
    "f01_breaking", "f02_live_developing", "f03_timeless", "f04_explanatory",
    "f05_data_investigative", "f06_author_voice", "f07_depth_analysis",
    "f08_expert_quotes", "f09_emotional_positive", "f10_conflict_tragedy",
    "f11_light_humor", "f12_actionable_steps", "f13_collective_call",
    "f14_community_identity", "f15_listicle_format", "f16_social_buzz",
]


def _features(active: set[str]) -> ArticleFeatures:
    return ArticleFeatures.model_validate(
        {n: {"status": 1 if n in active else 0, "reasoning": ""} for n in _NAMES}
    )


def test_actionable_howto_ranks_help_me_top() -> None:
    # f12_actionable_steps + f03_timeless → "Help me" must_have_all satisfied + booster
    ranked = rank_user_needs(_features({"f12_actionable_steps", "f03_timeless"}))
    assert ranked[0].category == "Help me"
    assert ranked[0].score > ranked[1].score


def test_returns_all_eight_categories_sorted() -> None:
    ranked = rank_user_needs(_features(set()))
    assert len(ranked) == 8
    assert ranked == sorted(ranked, key=lambda s: s.score, reverse=True)


def test_reject_rule_zeroes_score() -> None:
    # "Help me" rejects if f13_collective_call is set
    ranked = rank_user_needs(_features({"f12_actionable_steps", "f13_collective_call"}))
    help_me = next(s for s in ranked if s.category == "Help me")
    assert help_me.score == 0.0
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_category.py -v`
Expected: FAIL with `ModuleNotFoundError`/`ImportError` until Step 1's dicts are pasted in.

- [ ] **Step 4: Paste the dicts, run to verify it passes**

After pasting `TEMPO_REFERENCE_VECTORS` and `LOGIC_RULES`, run the same command.
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd backend && git add packages/analyst/src/analyst/category.py packages/analyst/tests/test_category.py
git commit -m "feat(analyst): port pure-python user-need rule engine"
```

---

### Task 4: LLM client + structured-output helper

**Files:**
- Create: `backend/packages/analyst/src/analyst/llm.py`
- Create: `backend/packages/analyst/tests/test_llm.py`

**Interfaces:**
- Consumes: `analyst.config.settings`.
- Produces:
  - `complete_structured(client, model: str, messages: list[dict], schema: type[T]) -> T` — sends `messages` (with the JSON schema appended to the system role), parses JSON, validates into `schema`, retries once on invalid output.
  - `complete_for_task(task: str, messages: list[dict], schema: type[T]) -> T` — resolves model + base_url from config, builds a cached client, delegates to `complete_structured`. **This is the function services monkeypatch in tests.**

- [ ] **Step 1: Write the module**

Create `backend/packages/analyst/src/analyst/llm.py`:

```python
import json
import logging
from functools import lru_cache
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from analyst.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=8)
def get_async_client(base_url: str, api_key: str, timeout: float) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=base_url, api_key=api_key or "not-needed", timeout=timeout)


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
    client: Any,
    model: str,
    messages: list[dict[str, str]],
    schema: type[T],
) -> T:
    augmented = _augment(messages, schema)
    last_exc: Exception | None = None
    for attempt in (1, 2):
        response = await client.chat.completions.create(
            model=model,
            messages=augmented,
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        try:
            return schema.model_validate_json(_extract_json(raw))
        except (ValidationError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning(
                "analyst llm returned invalid structured output",
                extra={"attempt": attempt, "schema": schema.__name__},
            )
    raise ValueError(f"LLM returned invalid output for {schema.__name__}: {last_exc}")


async def complete_for_task(
    task: str, messages: list[dict[str, str]], schema: type[T]
) -> T:
    client = get_async_client(
        settings.base_url_for(task),
        settings.analyst_llm_api_key,
        settings.analyst_request_timeout_seconds,
    )
    return await complete_structured(client, settings.model_for(task), messages, schema)
```

- [ ] **Step 2: Write the failing test**

Create `backend/packages/analyst/tests/test_llm.py`:

```python
import pytest
from analyst.llm import complete_structured
from analyst.schemas import RecommendationInsight


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[dict] = []

    async def create(self, **kwargs: object) -> _Completion:
        self.calls.append(kwargs)
        return _Completion(self._contents[len(self.calls) - 1])


class _Chat:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _Completions(contents)


class FakeClient:
    def __init__(self, contents: list[str]) -> None:
        self.chat = _Chat(contents)


async def test_parses_valid_json() -> None:
    client = FakeClient(['{"title":"t","insight":"i","action":"a"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.title == "t"


async def test_strips_code_fences() -> None:
    client = FakeClient(['```json\n{"title":"t","insight":"i","action":"a"}\n```'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.action == "a"


async def test_retries_once_then_succeeds() -> None:
    client = FakeClient(["not json", '{"title":"t","insight":"i","action":"a"}'])
    result = await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
    assert result.insight == "i"
    assert len(client.chat.completions.calls) == 2


async def test_raises_after_two_failures() -> None:
    client = FakeClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        await complete_structured(client, "m", [{"role": "user", "content": "x"}], RecommendationInsight)
```

- [ ] **Step 3: Run to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_llm.py -v`
Expected: PASS (4 tests). (`asyncio_mode = "auto"` makes the async tests run without decorators.)

- [ ] **Step 4: Commit**

```bash
cd backend && git add packages/analyst/src/analyst/llm.py packages/analyst/tests/test_llm.py
git commit -m "feat(analyst): openai-compatible client + structured-output helper"
```

---

### Task 5: Analyze service

**Files:**
- Create: `backend/packages/analyst/src/analyst/analyze.py`
- Create: `backend/packages/analyst/tests/test_analyze.py`

**Interfaces:**
- Consumes: `analyst.llm.complete_for_task`, `analyst.category.rank_user_needs`, schemas.
- Produces:
  - `run_analysis(title: str, content: str) -> AnalyzeResult`
  - `run_analysis_batch(articles: list[ArticleRequest]) -> list[AnalyzeResult]` (bounded concurrency = 3)

- [ ] **Step 1: Write the module**

Create `backend/packages/analyst/src/analyst/analyze.py`. Copy the `SYSTEM_PROMPT` string verbatim from `user-need/data-user-need-backend/services.py` (lines 7–67) into the marked spot:

```python
import asyncio

from analyst import llm
from analyst.category import rank_user_needs
from analyst.schemas import (
    AnalyzeResult,
    ArticleAnalysisResult,
    ArticleRequest,
)

SYSTEM_PROMPT = """..."""  # <-- paste services.py lines 7-67 verbatim

_BATCH_CONCURRENCY = asyncio.Semaphore(3)


async def run_analysis(title: str, content: str) -> AnalyzeResult:
    parsed = await llm.complete_for_task(
        "analyze",
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"title:{title} \n content: {content}"},
        ],
        ArticleAnalysisResult,
    )
    ranked = rank_user_needs(parsed.features)
    return AnalyzeResult(
        features=parsed.features,
        editorial_feedback=parsed.feedback,
        user_needs=ranked[:2],
    )


async def _run_one(article: ArticleRequest) -> AnalyzeResult:
    async with _BATCH_CONCURRENCY:
        return await run_analysis(article.title, article.content)


async def run_analysis_batch(articles: list[ArticleRequest]) -> list[AnalyzeResult]:
    return await asyncio.gather(*(_run_one(a) for a in articles))
```

- [ ] **Step 2: Write the failing test**

Create `backend/packages/analyst/tests/test_analyze.py`:

```python
import pytest
from analyst import analyze
from analyst.schemas import ArticleAnalysisResult, ArticleRequest

_NAMES = [
    "f01_breaking", "f02_live_developing", "f03_timeless", "f04_explanatory",
    "f05_data_investigative", "f06_author_voice", "f07_depth_analysis",
    "f08_expert_quotes", "f09_emotional_positive", "f10_conflict_tragedy",
    "f11_light_humor", "f12_actionable_steps", "f13_collective_call",
    "f14_community_identity", "f15_listicle_format", "f16_social_buzz",
]


def _canned(active: set[str]) -> ArticleAnalysisResult:
    return ArticleAnalysisResult.model_validate(
        {
            "features": {
                n: {"status": 1 if n in active else 0, "reasoning": ""} for n in _NAMES
            },
            "feedback": {
                "recommendation_judul": ["Judul"], "missing_info": [],
                "bias_check": [], "next_angle": [],
            },
        }
    )


@pytest.fixture
def patched_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(task: str, messages: list[dict], schema: type) -> ArticleAnalysisResult:
        assert task == "analyze"
        return _canned({"f12_actionable_steps", "f03_timeless"})

    monkeypatch.setattr(analyze.llm, "complete_for_task", fake)


async def test_run_analysis_returns_two_user_needs(patched_llm: None) -> None:
    result = await analyze.run_analysis("t", "c")
    assert len(result.user_needs) == 2
    assert result.user_needs[0].category == "Help me"
    assert result.editorial_feedback.recommendation_judul == ["Judul"]


async def test_batch_runs_all(patched_llm: None) -> None:
    results = await analyze.run_analysis_batch(
        [ArticleRequest(title="t", content="c"), ArticleRequest(title="t2", content="c2")]
    )
    assert len(results) == 2
    assert all(r.user_needs[0].category == "Help me" for r in results)
```

- [ ] **Step 3: Run to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_analyze.py -v`
Expected: PASS (2 tests). If it fails with an empty `SYSTEM_PROMPT`, confirm lines 7–67 were pasted.

- [ ] **Step 4: Commit**

```bash
cd backend && git add packages/analyst/src/analyst/analyze.py packages/analyst/tests/test_analyze.py
git commit -m "feat(analyst): article analysis service (16 features + user-need ranking)"
```

---

### Task 6: Recommendation service

**Files:**
- Create: `backend/packages/analyst/src/analyst/recommend.py`
- Create: `backend/packages/analyst/src/analyst/data/airflow_data.json` (copied)
- Create: `backend/packages/analyst/tests/test_recommend.py`

**Interfaces:**
- Consumes: `analyst.llm.complete_for_task`, schemas (`DataFilterParameters`, `RecommendationInsightsLLM`, `RecommendationOutput`, `RecommendationRequest`).
- Produces:
  - `run_recommendation(request: RecommendationRequest) -> RecommendationOutput`
  - `_apply_filters(data: list[dict], filters: DataFilterParameters) -> list[dict]`
  - `_load_data() -> list[dict]`

- [ ] **Step 1: Copy the dataset into the package**

```bash
mkdir -p backend/packages/analyst/src/analyst/data
cp user-need/data-user-need-backend/airflow_data.json backend/packages/analyst/src/analyst/data/airflow_data.json
```

- [ ] **Step 2: Write the module**

Create `backend/packages/analyst/src/analyst/recommend.py`. Copy `_apply_filters` verbatim from `user-need/data-user-need-backend/recommendation_service.py` (lines 136–188), and copy the two system prompts (`_SELECTOR_SYSTEM` lines 56–63, `_INSIGHT_SYSTEM` lines 79–89) into the marked spots:

```python
import json
import logging
from datetime import datetime
from pathlib import Path

from analyst import llm
from analyst.schemas import (
    DataFilterParameters,
    RecommendationInsightsLLM,
    RecommendationOutput,
    RecommendationRequest,
)

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent / "data" / "airflow_data.json"

_SELECTOR_SYSTEM = """..."""  # <-- paste recommendation_service.py lines 56-63
_INSIGHT_SYSTEM = """..."""   # <-- paste recommendation_service.py lines 79-89


def _load_data() -> list[dict]:
    try:
        return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("analyst recommendation dataset missing", extra={"path": str(_DATA_PATH)})
        return []
    except json.JSONDecodeError:
        logger.error("analyst recommendation dataset is not valid JSON")
        return []


def _apply_filters(data: list[dict], filters: DataFilterParameters) -> list[dict]:
    ...  # <-- paste recommendation_service.py lines 137-188 (body of _apply_filters) verbatim


async def run_recommendation(request: RecommendationRequest) -> RecommendationOutput:
    filters = await llm.complete_for_task(
        "recommend",
        [
            {"role": "system", "content": _SELECTOR_SYSTEM},
            {"role": "user", "content": f"User intent: {request.intent}"},
        ],
        DataFilterParameters,
    )

    rows = _apply_filters(_load_data(), filters)
    filters_dict = filters.model_dump(exclude_none=True)

    insights = await llm.complete_for_task(
        "recommend",
        [
            {"role": "system", "content": _INSIGHT_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Filters applied:\n{json.dumps(filters_dict, indent=2)}\n\n"
                    f"Data (JSON rows):\n{json.dumps(rows[:20], ensure_ascii=False, indent=2)}\n\n"
                    f"User's original intent: {request.intent}"
                ),
            },
        ],
        RecommendationInsightsLLM,
    )

    return RecommendationOutput(
        filters_applied=filters_dict,
        sample_data=rows,
        insights=insights.insights,
        summary=insights.summary,
        data_source="airflow_json",
    )
```

Note: `_apply_filters` references `datetime.now()` for `days_lookback`; keep the ported `import datetime` usage. The function is pure given a fixed `data` argument in tests (the lookback branch is only hit when `days_lookback` is set).

- [ ] **Step 3: Write the failing test**

Create `backend/packages/analyst/tests/test_recommend.py`:

```python
import pytest
from analyst import recommend
from analyst.schemas import (
    DataFilterParameters,
    RecommendationInsight,
    RecommendationInsightsLLM,
    RecommendationRequest,
)

_ROWS = [
    {"rubrics_sb": "Politik", "total_views": 5000, "user_need_model": "Update me"},
    {"rubrics_sb": "Olahraga", "total_views": 100, "user_need_model": "Divert me"},
    {"rubrics_sb": "Politik", "total_views": 50, "user_need_model": "Educate me"},
]


def test_apply_filters_category_and_minviews() -> None:
    filtered = recommend._apply_filters(
        _ROWS, DataFilterParameters(category="politik", min_page_views=1000)
    )
    assert len(filtered) == 1
    assert filtered[0]["total_views"] == 5000


def test_apply_filters_sorts_by_views_desc() -> None:
    filtered = recommend._apply_filters(_ROWS, DataFilterParameters())
    views = [r["total_views"] for r in filtered]
    assert views == sorted(views, reverse=True)


async def test_run_recommendation_two_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recommend, "_load_data", lambda: _ROWS)

    async def fake(task: str, messages: list[dict], schema: type):
        assert task == "recommend"
        if schema is DataFilterParameters:
            return DataFilterParameters(category="Politik", min_page_views=1000)
        return RecommendationInsightsLLM(
            insights=[RecommendationInsight(title="t", insight="i", action="a")],
            summary="ringkasan",
        )

    monkeypatch.setattr(recommend.llm, "complete_for_task", fake)

    out = await recommend.run_recommendation(RecommendationRequest(intent="politik viral"))
    assert out.summary == "ringkasan"
    assert out.data_source == "airflow_json"
    assert out.filters_applied == {"category": "Politik", "min_page_views": 1000}
    assert len(out.insights) == 1
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests/test_recommend.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd backend && git add packages/analyst/src/analyst/recommend.py packages/analyst/src/analyst/data packages/analyst/tests/test_recommend.py
git commit -m "feat(analyst): recommendation pipeline on unified client (no langchain)"
```

---

### Task 7: API routes

**Files:**
- Create: `backend/packages/api/src/api/routes/analyst.py`
- Create: `backend/packages/api/tests/test_analyst.py`
- Modify: `backend/packages/api/src/api/main.py:7` (import) and `:31` (register router)
- Modify: `backend/packages/api/pyproject.toml:6-13` (add `analyst` dep) and `:15-16` (add source)

**Interfaces:**
- Consumes: `analyst.analyze.run_analysis`, `analyst.analyze.run_analysis_batch`, `analyst.recommend.run_recommendation`, schemas.
- Produces routes under `/api/v1/analyst`: `POST /analyze` → `AnalyzeResult`; `POST /analyze/batch` → `list[AnalyzeResult]`; `POST /recommendation` → `RecommendationOutput`.

- [ ] **Step 1: Add the workspace dependency**

In `backend/packages/api/pyproject.toml`, add `"analyst"` to the `dependencies` list (after `"core"`) and add the source mapping:

```toml
dependencies = [
  "core",
  "analyst",
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "python-json-logger>=2.0",
  "sqlalchemy>=2",
  "pydantic>=2",
]

[tool.uv.sources]
core = { workspace = true }
analyst = { workspace = true }
```

Then re-sync: `cd backend && uv lock && uv sync`.

- [ ] **Step 2: Write the route module**

Create `backend/packages/api/src/api/routes/analyst.py`:

```python
import logging

from analyst import analyze, recommend
from analyst.schemas import (
    AnalyzeResult,
    ArticleRequest,
    BatchArticleRequest,
    RecommendationOutput,
    RecommendationRequest,
)
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.post("/analyze", response_model=AnalyzeResult, summary="Score one article on 16 editorial features + user needs")
async def analyze_article(body: ArticleRequest) -> AnalyzeResult:
    try:
        return await analyze.run_analysis(body.title, body.content)
    except Exception as exc:
        logger.error("analyst analyze failed", exc_info=True)
        raise HTTPException(status_code=502, detail="Analysis failed") from exc


@router.post("/analyze/batch", response_model=list[AnalyzeResult], summary="Score a batch of articles")
async def analyze_batch(body: BatchArticleRequest) -> list[AnalyzeResult]:
    try:
        return await analyze.run_analysis_batch(body.articles)
    except Exception as exc:
        logger.error("analyst batch analyze failed", exc_info=True)
        raise HTTPException(status_code=502, detail="Batch analysis failed") from exc


@router.post("/recommendation", response_model=RecommendationOutput, summary="Editorial recommendation insights from a free-text intent")
async def recommendation(body: RecommendationRequest) -> RecommendationOutput:
    try:
        return await recommend.run_recommendation(body)
    except Exception as exc:
        logger.error("analyst recommendation failed", exc_info=True)
        raise HTTPException(status_code=502, detail="Recommendation failed") from exc
```

- [ ] **Step 3: Register the router**

In `backend/packages/api/src/api/main.py`, add `analyst` to the import on line 7 and one `include_router` line:

```python
from api.routes import analyst, articles, clusters, health, pipeline, sources, trend_signals
```
```python
app.include_router(analyst.router, prefix="/api/v1")
```

- [ ] **Step 4: Write the failing test**

Create `backend/packages/api/tests/test_analyst.py`. The module-local `client` fixture shadows the DB-bound one in `conftest.py` (analyst routes use no DB):

```python
import pytest
from analyst import analyze, recommend
from analyst.schemas import (
    AnalyzeResult,
    ArticleAnalysisResult,
    RecommendationInsight,
    RecommendationOutput,
    UserNeedScore,
)
from api.main import app
from httpx import ASGITransport, AsyncClient

_NAMES = [
    "f01_breaking", "f02_live_developing", "f03_timeless", "f04_explanatory",
    "f05_data_investigative", "f06_author_voice", "f07_depth_analysis",
    "f08_expert_quotes", "f09_emotional_positive", "f10_conflict_tragedy",
    "f11_light_humor", "f12_actionable_steps", "f13_collective_call",
    "f14_community_identity", "f15_listicle_format", "f16_social_buzz",
]


def _analyze_result() -> AnalyzeResult:
    parsed = ArticleAnalysisResult.model_validate(
        {
            "features": {n: {"status": 0, "reasoning": ""} for n in _NAMES},
            "feedback": {
                "recommendation_judul": ["J"], "missing_info": [],
                "bias_check": [], "next_angle": [],
            },
        }
    )
    return AnalyzeResult(
        features=parsed.features,
        editorial_feedback=parsed.feedback,
        user_needs=[UserNeedScore(category="Help me", score=80.0)],
    )


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_analyze_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(title: str, content: str) -> AnalyzeResult:
        return _analyze_result()

    monkeypatch.setattr(analyze, "run_analysis", fake)
    resp = await client.post("/api/v1/analyst/analyze", json={"title": "t", "content": "c"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_needs"][0]["category"] == "Help me"
    assert body["features"]["f01_breaking"]["status"] == 0


async def test_recommendation_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(request) -> RecommendationOutput:
        return RecommendationOutput(
            filters_applied={"category": "Politik"},
            sample_data=[],
            insights=[RecommendationInsight(title="t", insight="i", action="a")],
            summary="s",
            data_source="airflow_json",
        )

    monkeypatch.setattr(recommend, "run_recommendation", fake)
    resp = await client.post("/api/v1/analyst/recommendation", json={"intent": "politik viral"})
    assert resp.status_code == 200
    assert resp.json()["summary"] == "s"


async def test_analyze_failure_maps_to_502(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(title: str, content: str) -> AnalyzeResult:
        raise RuntimeError("llm down")

    monkeypatch.setattr(analyze, "run_analysis", boom)
    resp = await client.post("/api/v1/analyst/analyze", json={"title": "t", "content": "c"})
    assert resp.status_code == 502
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest packages/api/tests/test_analyst.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Verify the OpenAPI contract exposes the new paths**

Run:
```bash
cd backend && ./.venv/bin/python -c "from api.main import app; import json; print([p for p in app.openapi()['paths'] if 'analyst' in p])"
```
Expected: `['/api/v1/analyst/analyze', '/api/v1/analyst/analyze/batch', '/api/v1/analyst/recommendation']`

- [ ] **Step 7: Commit**

```bash
cd backend && git add packages/api/src/api/routes/analyst.py packages/api/src/api/main.py packages/api/pyproject.toml packages/api/tests/test_analyst.py uv.lock
git commit -m "feat(api): mount /api/v1/analyst analyze + recommendation endpoints"
```

---

### Task 8: Docker, docs, and decision log

**Files:**
- Modify: `backend/Dockerfile` (deps stage + api-build stage + api-dev reload dir)
- Modify: `docs/tech-stack.md` (add `openai`)
- Modify: `docs/decisions.md` (append D37)
- Modify: `CLAUDE.md` (module table + API endpoints line)

- [ ] **Step 1: Add `analyst` to the Docker deps stage**

In `backend/Dockerfile`, after the `scoring` pyproject COPY (line 24), add:

```dockerfile
COPY packages/analyst/pyproject.toml     packages/analyst/pyproject.toml
```

- [ ] **Step 2: Add `analyst` source to the api-build stage**

In `backend/Dockerfile`, in the `api-build` stage, add the analyst source COPY between the core and api source copies (around lines 31–32):

```dockerfile
COPY packages/core/src    packages/core/src
COPY packages/analyst/src packages/analyst/src
COPY packages/api/src     packages/api/src
```

- [ ] **Step 3: Add the api-dev reload dir**

In `backend/Dockerfile`, in the `api-dev` CMD (after the `/app/packages/api/src` reload-dir line ~61), add:

```dockerfile
     "--reload-dir", "/app/packages/analyst/src", \
```

(Place it before the closing `]` of the CMD list; ensure the preceding line keeps its trailing comma + backslash.)

- [ ] **Step 4: Verify the dev compose mounts the package**

Run:
```bash
cd backend && grep -nE "packages|volumes" docker-compose.yml | grep -i analyst || grep -nE "\./packages" docker-compose.yml
```
Expected: either an explicit analyst mount or a blanket `./packages:/app/packages` mount (which already covers it). If neither, add the analyst source mount to the `api` service to match the others.

- [ ] **Step 5: Verify the api image still resolves without ML deps**

Run:
```bash
cd backend && uv sync --package api --frozen && ./.venv/bin/python -c "import api.main; import openai; print('api ok, openai', openai.__version__)"
```
Expected: prints `api ok, openai <version>`. (Confirms `analyst` + `openai` install under the `api` package and no torch is pulled.)

- [ ] **Step 6: Update tech-stack docs**

In `docs/tech-stack.md`, add a row/line documenting the new top-level dependency: `openai` (OpenAI-compatible SDK) used by the `analyst` package; note "local vs API = base-URL swap, no torch". Match the file's existing format.

- [ ] **Step 7: Append the decision-log entry**

Append to `docs/decisions.md` the D37 entry (use the block in `docs/superpowers/specs/2026-06-18-embed-editorial-analyst-design.md`, "Proposed decision-log entry" section). Follow the file's Context/Options/Decision/Rationale/Implication format.

- [ ] **Step 8: Update CLAUDE.md**

In `CLAUDE.md`:
- Add a row to the Modules table: `| analyst | Editorial AI Analyst: article scoring + recommendation | openai SDK; OpenAI-compatible; no ML import |`
- In the API endpoints section, add the three `/api/v1/analyst/*` POST endpoints (note: write surface, but stateless — no DB writes).

- [ ] **Step 9: Run the full backend suite**

Run: `cd backend && ./.venv/bin/python -m pytest packages/analyst/tests packages/api/tests -v`
Expected: all green.

- [ ] **Step 10: Commit**

```bash
cd backend && git add Dockerfile docker-compose.yml ../docs/tech-stack.md ../docs/decisions.md ../CLAUDE.md
git commit -m "chore(analyst): docker wiring, tech-stack, D37 decision, CLAUDE.md"
```

---

## Self-Review

**Spec coverage:**
- New self-contained `analyst` package → Tasks 1–6. ✓
- Per-task local/API config (base-URL swap) → Task 1 (`config.py`), Task 4 (`complete_for_task`). ✓
- 16-feature analyze + pure rule engine → Tasks 3, 5. ✓
- Recommendation without LangChain, static dataset → Task 6. ✓
- API routes with OpenAPI contract → Task 7. ✓
- `api` stays ML-free; `analyst` depends only on `core` → enforced by pyproject (Tasks 1, 7), verified Task 8 Step 5. ✓
- No daemon/pipeline involvement, no DB tables/migration → nothing in the plan touches `pipeline` or Alembic. ✓
- Docker + tech-stack + D37 + CLAUDE.md → Task 8. ✓
- Deferred (LangChain/BigQuery/Lambda/slowapi/auth) → never introduced. ✓

**Placeholder scan:** The only `...`/"paste" markers are explicit verbatim copies from named in-repo source files with exact line numbers (SYSTEM_PROMPT, the two recommendation prompts, `_apply_filters`, the two rule dicts, the ported `schemas.py`). These are concrete copy instructions, not vague TODOs.

**Type consistency:** `AnalyzeResult{features,editorial_feedback,user_needs}`, `rank_user_needs -> list[UserNeedScore]`, `complete_for_task(task, messages, schema)`, `run_analysis(title, content) -> AnalyzeResult`, `run_recommendation(request) -> RecommendationOutput` are used identically across Tasks 3–7. Route response models match service return types. ✓

## Follow-up: Frontend plan

After these tasks land and the API is live, Plan 2 covers the frontend: regenerate `@ei-fe/api` from the new `/openapi.json`, build a new `@ei-fe/features/analyst` feature (analyze + recommendation + chat views on `@ei-fe/ui`), and add the route + nav in `@ei-fe/app`. It is deliberately deferred because the generated client types depend on the endpoints existing first.
