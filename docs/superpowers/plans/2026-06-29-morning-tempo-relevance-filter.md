# Morning Tempo-Relevance Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-filter `/clusters/morning` so it only returns clusters whose LLM-assigned desk is in an allow-list AND whose user-need is not in a deny-list.

**Architecture:** The daily `labeling` step's existing per-cluster LLM call is extended to also emit `desk_category` and `user_need_category`. These are stored raw on `ClusterInsight`; the `/morning` endpoint applies the allow/deny policy at read-time from config. No new pipeline step, no new LLM calls.

**Tech Stack:** Python 3.11, SQLAlchemy 2 (async ORM), Alembic, FastAPI, Pydantic v2, pydantic-settings, pytest/pytest-asyncio, Postgres (pgvector). uv workspace under `backend/`.

## Global Constraints

- All backend commands run from `backend/`.
- `api` package never imports ML modules; batch modules never import each other — shared code lives in `core` or `llm`. The taxonomy that both `labeling` and the API need therefore lives in `core`.
- Classification is **computed and stored for all clusters**; only `/morning` filters on it. Do not add the filter to `/bento`, `/deferred`, `/quadrant`, or `/current`.
- No `tempo_relevant` boolean column — store raw categories, filter at read-time against config so policy changes need no re-label.
- New columns are nullable; NULL classification is excluded from `/morning` by construction (this is intended).
- DB-backed tests run against a real Postgres via `docker compose` from `backend/`. The migration MUST be applied to that DB before column-dependent tests pass. The test fixtures (`api/tests/conftest.py`, `labeling/tests/conftest.py`) do NOT create tables — they assume migrations are applied.
- No `print()`; logging is JSON via `core.logging`. Follow existing module patterns.
- Default `labeling_provider` is `"api"`; the `"local"` (Gemma) path still exists and must keep parity.
- Allowed desks default: `Politik, Hukum, Nasional, Ekonomi & Bisnis, Internasional, Investigasi, Sains & Teknologi, Lingkungan`. Denied user-needs default: `Divert me, Keep me engaged`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `backend/packages/core/src/core/taxonomy.py` (new) | Canonical desk + user-need value sets and `normalize_*` coercers | 1 |
| `backend/packages/core/tests/test_taxonomy.py` (new) | Unit tests for taxonomy coercers | 1 |
| `backend/packages/core/src/core/config.py` | Add `morning_allowed_desks`, `morning_denied_user_needs` | 2 |
| `backend/packages/core/tests/test_config.py` | Assert new config defaults | 2 |
| `backend/packages/core/src/core/models.py` | Add 2 columns to `ClusterInsight` | 3 |
| `backend/alembic/versions/<rev>_*.py` (new) | Migration for the 2 columns | 3 |
| `backend/packages/labeling/src/labeling/schemas.py` | Add 2 fields to `ClusterInsightLLM` | 4 |
| `backend/packages/labeling/src/labeling/prompts.py` | Ask the LLM (API + local prompts) for desk + user-need | 4, 5 |
| `backend/packages/labeling/src/labeling/llm.py` | Local-path regex + parser for new fields | 5 |
| `backend/packages/labeling/src/labeling/pipeline.py` | Persist coerced classification via `_upsert_insight` | 4 |
| `backend/packages/labeling/tests/test_schemas.py` | Schema accepts new fields | 4 |
| `backend/packages/labeling/tests/test_pipeline_classification.py` (new) | `_upsert_insight` persists classification | 4 |
| `backend/packages/labeling/tests/test_llm.py` | Local parser extracts DESK/KEBUTUHAN | 5 |
| `backend/packages/labeling/tests/test_prompts.py` | Prompts list valid desks/needs | 4, 5 |
| `backend/packages/api/src/api/routes/clusters.py` | `ClusterSummary` fields + `_to_summary` + `/morning` WHERE | 6 |
| `backend/packages/api/tests/test_clusters.py` | Helper defaults + exclusion tests | 6 |
| `docs/schema.dbml`, `backend/.env.example`, `CLAUDE.md` | Doc mirrors | 7 |

---

## Task 1: Shared taxonomy module in `core`

**Files:**
- Create: `backend/packages/core/src/core/taxonomy.py`
- Test: `backend/packages/core/tests/test_taxonomy.py`

**Interfaces:**
- Produces:
  - `DESK_CATEGORIES: tuple[str, ...]`
  - `USER_NEED_CATEGORIES: tuple[str, ...]`
  - `normalize_desk(value: str | None) -> str | None` — returns the canonical desk string (case-insensitive match) or `None`.
  - `normalize_user_need(value: str | None) -> str | None` — same for user-needs.

- [ ] **Step 1: Write the failing test**

Create `backend/packages/core/tests/test_taxonomy.py`:

```python
from core.taxonomy import (
    DESK_CATEGORIES,
    USER_NEED_CATEGORIES,
    normalize_desk,
    normalize_user_need,
)


def test_desk_categories_include_allowed_and_rejected():
    assert "Politik" in DESK_CATEGORIES
    assert "Hiburan" in DESK_CATEGORIES
    assert "Lainnya" in DESK_CATEGORIES


def test_user_need_categories_has_eight():
    assert len(USER_NEED_CATEGORIES) == 8
    assert "Update me" in USER_NEED_CATEGORIES
    assert "Divert me" in USER_NEED_CATEGORIES


def test_normalize_desk_canonicalizes_case_and_whitespace():
    assert normalize_desk("  politik ") == "Politik"
    assert normalize_desk("EKONOMI & BISNIS") == "Ekonomi & Bisnis"


def test_normalize_desk_rejects_unknown_and_empty():
    assert normalize_desk("Astrologi") is None
    assert normalize_desk("") is None
    assert normalize_desk(None) is None


def test_normalize_user_need_canonicalizes_and_rejects():
    assert normalize_user_need("update me") == "Update me"
    assert normalize_user_need("Bikin Senang") is None
    assert normalize_user_need(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm api pytest packages/core/tests/test_taxonomy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.taxonomy'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/packages/core/src/core/taxonomy.py`:

```python
"""Canonical editorial taxonomy shared by `labeling` (writes) and `api` (reads).

Lives in `core` because batch modules never import each other; both the
labeling pipeline and the API need the same value sets.
"""

DESK_CATEGORIES: tuple[str, ...] = (
    "Politik",
    "Hukum",
    "Nasional",
    "Ekonomi & Bisnis",
    "Internasional",
    "Investigasi",
    "Sains & Teknologi",
    "Lingkungan",
    "Hiburan",
    "Olahraga",
    "Lifestyle",
    "Selebriti",
    "Otomotif",
    "Lainnya",
)

USER_NEED_CATEGORIES: tuple[str, ...] = (
    "Update me",
    "Keep me engaged",
    "Educate me",
    "Give me perspective",
    "Inspire me",
    "Divert me",
    "Help me",
    "Connect me",
)

_DESK_BY_FOLD = {d.casefold(): d for d in DESK_CATEGORIES}
_NEED_BY_FOLD = {n.casefold(): n for n in USER_NEED_CATEGORIES}


def normalize_desk(value: str | None) -> str | None:
    if not value:
        return None
    return _DESK_BY_FOLD.get(value.strip().casefold())


def normalize_user_need(value: str | None) -> str | None:
    if not value:
        return None
    return _NEED_BY_FOLD.get(value.strip().casefold())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose run --rm api pytest packages/core/tests/test_taxonomy.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/core/taxonomy.py packages/core/tests/test_taxonomy.py
git commit -m "feat(core): canonical desk + user-need taxonomy with coercers"
```

---

## Task 2: Config policy lists

**Files:**
- Modify: `backend/packages/core/src/core/config.py:56` (insert after `scoring_morning_top_n`)
- Test: `backend/packages/core/tests/test_config.py`

**Interfaces:**
- Produces: `settings.morning_allowed_desks: list[str]`, `settings.morning_denied_user_needs: list[str]`

- [ ] **Step 1: Write the failing test**

Append to `backend/packages/core/tests/test_config.py`:

```python
def test_morning_filter_defaults():
    from core.config import Settings

    s = Settings(database_url="postgresql+asyncpg://x:x@localhost/x", _env_file=None)
    assert "Politik" in s.morning_allowed_desks
    assert "Hiburan" not in s.morning_allowed_desks
    assert "Divert me" in s.morning_denied_user_needs
    assert "Keep me engaged" in s.morning_denied_user_needs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm api pytest packages/core/tests/test_config.py::test_morning_filter_defaults -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'morning_allowed_desks'`

- [ ] **Step 3: Write minimal implementation**

In `backend/packages/core/src/core/config.py`, immediately after the line `scoring_morning_top_n: int = 10` (line 56), insert:

```python
    # Morning Tempo-relevance hard filter (read-time policy; tune via env without re-label).
    # Env override expects a JSON array, e.g. MORNING_ALLOWED_DESKS='["Politik","Hukum"]'.
    morning_allowed_desks: list[str] = [
        "Politik",
        "Hukum",
        "Nasional",
        "Ekonomi & Bisnis",
        "Internasional",
        "Investigasi",
        "Sains & Teknologi",
        "Lingkungan",
    ]
    morning_denied_user_needs: list[str] = ["Divert me", "Keep me engaged"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose run --rm api pytest packages/core/tests/test_config.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/core/config.py packages/core/tests/test_config.py
git commit -m "feat(core): morning allow/deny config for desk + user-need"
```

---

## Task 3: `ClusterInsight` columns + migration

**Files:**
- Modify: `backend/packages/core/src/core/models.py:425` (insert after `editorial_quadrant`)
- Create: `backend/alembic/versions/<autogen>_add_cluster_insight_desk_user_need.py`

**Interfaces:**
- Produces: `ClusterInsight.desk_category: str | None`, `ClusterInsight.user_need_category: str | None` (DB columns `desk_category`, `user_need_category`, both nullable text).

- [ ] **Step 1: Add the model columns**

In `backend/packages/core/src/core/models.py`, immediately after the line `editorial_quadrant: Mapped[str | None] = mapped_column(String)` (line 425), insert:

```python
    # Editorial fit classification (LLM, written by labeling step). Filtered at read-time by /morning.
    desk_category: Mapped[str | None] = mapped_column(String)
    user_need_category: Mapped[str | None] = mapped_column(String)
```

- [ ] **Step 2: Autogenerate the migration**

Run:
```bash
docker compose up -d postgres
docker compose run --rm api alembic revision --autogenerate -m "add cluster_insight desk_category user_need_category"
```
Expected: a new file under `backend/alembic/versions/` whose `upgrade()` contains:

```python
op.add_column('cluster_insight', sa.Column('desk_category', sa.String(), nullable=True))
op.add_column('cluster_insight', sa.Column('user_need_category', sa.String(), nullable=True))
```
and whose `downgrade()` drops both columns. Open the file and verify only these two `add_column` ops are present (autogenerate sometimes picks up unrelated drift — if it does, delete the spurious ops so the migration adds exactly these two columns).

- [ ] **Step 3: Apply the migration**

Run:
```bash
docker compose run --rm api alembic upgrade head
```
Expected: `Running upgrade ... -> <rev>, add cluster_insight desk_category user_need_category`

- [ ] **Step 4: Verify the columns exist**

Run:
```bash
docker compose run --rm api python -c "import asyncio; from sqlalchemy import text; from core.db import get_session;
async def m():
    async with get_session() as s:
        r = await s.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='cluster_insight' AND column_name IN ('desk_category','user_need_category')\"))
        print(sorted(c[0] for c in r.all()))
asyncio.run(m())"
```
Expected: `['desk_category', 'user_need_category']`

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/core/models.py alembic/versions/
git commit -m "feat(core): add desk_category + user_need_category to cluster_insight"
```

---

## Task 4: Labeling — emit & persist classification (API path)

**Files:**
- Modify: `backend/packages/labeling/src/labeling/schemas.py:4-9`
- Modify: `backend/packages/labeling/src/labeling/prompts.py` (`_CLUSTER_INSIGHT_USER_API`, line 90-97)
- Modify: `backend/packages/labeling/src/labeling/pipeline.py` (`_upsert_insight` line 188, `run()` line 294-306)
- Test: `backend/packages/labeling/tests/test_schemas.py`, `backend/packages/labeling/tests/test_prompts.py`, new `backend/packages/labeling/tests/test_pipeline_classification.py`

**Interfaces:**
- Consumes: `core.taxonomy.normalize_desk`, `core.taxonomy.normalize_user_need`, `core.taxonomy.DESK_CATEGORIES`, `core.taxonomy.USER_NEED_CATEGORIES` (Task 1); `ClusterInsight.desk_category` / `.user_need_category` (Task 3).
- Produces: `ClusterInsightLLM.desk_category: str | None`, `ClusterInsightLLM.user_need_category: str | None`; `_upsert_insight(..., desk_category=None, user_need_category=None)`.

- [ ] **Step 1: Write the failing schema test**

Replace the body of `test_cluster_insight_parses_full_payload` and `test_cluster_insight_minimal` in `backend/packages/labeling/tests/test_schemas.py` so they expect the new fields:

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
            "desk_category": "Ekonomi & Bisnis",
            "user_need_category": "Update me",
        }
    )
    d = m.model_dump()
    assert d["desk_category"] == "Ekonomi & Bisnis"
    assert d["user_need_category"] == "Update me"
    assert set(d) == {
        "label", "what_happened", "parties_involved", "editorial_angle",
        "summary", "desk_category", "user_need_category",
    }


def test_cluster_insight_minimal() -> None:
    m = ClusterInsightLLM.model_validate({"label": "X"})
    assert m.model_dump() == {
        "label": "X",
        "what_happened": None,
        "parties_involved": None,
        "editorial_angle": None,
        "summary": None,
        "desk_category": None,
        "user_need_category": None,
    }


def test_cluster_label() -> None:
    assert ClusterLabelLLM.model_validate({"label": "Topik singkat"}).label == "Topik singkat"
```

- [ ] **Step 2: Run schema test to verify it fails**

Run: `docker compose run --rm api pytest packages/labeling/tests/test_schemas.py -v`
Expected: FAIL — `desk_category` not in dump / `set(d)` mismatch.

- [ ] **Step 3: Add the schema fields**

In `backend/packages/labeling/src/labeling/schemas.py`, replace the `ClusterInsightLLM` class:

```python
class ClusterInsightLLM(BaseModel):
    label: str
    what_happened: str | None = None
    parties_involved: list[str] | None = None
    editorial_angle: str | None = None
    summary: list[str] | None = None
    desk_category: str | None = None
    user_need_category: str | None = None
```

- [ ] **Step 4: Run schema test to verify it passes**

Run: `docker compose run --rm api pytest packages/labeling/tests/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing prompt test**

Append to `backend/packages/labeling/tests/test_prompts.py`:

```python
def test_cluster_insight_api_prompt_lists_desk_and_user_need() -> None:
    msgs = format_cluster_insight_messages_api(
        [{"title": "Sidang korupsi", "first_paragraph": "Terdakwa hadir."}]
    )
    body = msgs[0]["content"]
    assert "Politik" in body and "Hiburan" in body  # desk options listed
    assert "Update me" in body and "Divert me" in body  # user-need options listed
```

- [ ] **Step 6: Run prompt test to verify it fails**

Run: `docker compose run --rm api pytest packages/labeling/tests/test_prompts.py::test_cluster_insight_api_prompt_lists_desk_and_user_need -v`
Expected: FAIL — desk names absent from prompt body.

- [ ] **Step 7: Extend the API prompt**

In `backend/packages/labeling/src/labeling/prompts.py`, add an import at the top of the file (after any existing imports; the file currently has none, so add at line 1):

```python
from core.taxonomy import DESK_CATEGORIES, USER_NEED_CATEGORIES

_DESK_OPTIONS = ", ".join(DESK_CATEGORIES)
_USER_NEED_OPTIONS = ", ".join(USER_NEED_CATEGORIES)
```

Then replace `_CLUSTER_INSIGHT_USER_API` (lines 90-97) with:

```python
_CLUSTER_INSIGHT_USER_API = (
    "{system_prompt}\n\n"
    "Berikut {count} sudut liputan berbeda dari satu klaster berita yang sama:\n\n"
    "{articles}\n\n"
    "Hasilkan ringkasan editorial: label topik 5 sampai 7 kata tanpa tanda baca, "
    "apa yang terjadi dalam 1 sampai 2 kalimat, daftar pihak atau tokoh utama, "
    "satu kalimat sudut editorial untuk redaksi, dan beberapa klaim fakta penting. "
    "Tentukan juga desk_category, pilih TEPAT SATU dari: " + _DESK_OPTIONS + ". "
    "Dan user_need_category, pilih TEPAT SATU dari: " + _USER_NEED_OPTIONS + ". "
    "Jika tidak yakin, pilih desk 'Lainnya'."
)
```

- [ ] **Step 8: Run prompt test to verify it passes**

Run: `docker compose run --rm api pytest packages/labeling/tests/test_prompts.py -v`
Expected: PASS (including the pre-existing prompt tests)

- [ ] **Step 9: Write the failing pipeline-persist test**

Create `backend/packages/labeling/tests/test_pipeline_classification.py`:

```python
import uuid

import pytest
from core.db import get_session
from core.models import ArticleCluster, ClusterInsight, ClusterRun
from labeling.pipeline import _upsert_insight
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def test_upsert_insight_persists_classification(clean_db) -> None:
    async with get_session() as session:
        run = ClusterRun(id=uuid.uuid4())
        cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, is_current=True)
        session.add_all([run, cluster])
        await session.flush()

        await _upsert_insight(
            session,
            cluster.id,
            what_happened=None,
            parties_involved=None,
            editorial_angle=None,
            summary=None,
            desk_category="Politik",
            user_need_category="Update me",
        )
        await session.commit()

        row = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one()
        assert row.desk_category == "Politik"
        assert row.user_need_category == "Update me"


async def test_upsert_insight_none_classification_left_unset(clean_db) -> None:
    async with get_session() as session:
        run = ClusterRun(id=uuid.uuid4())
        cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, is_current=True)
        session.add_all([run, cluster])
        await session.flush()

        await _upsert_insight(
            session, cluster.id, None, None, None, None,
            desk_category=None, user_need_category=None,
        )
        await session.commit()

        row = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one()
        assert row.desk_category is None
        assert row.user_need_category is None
```

- [ ] **Step 10: Run pipeline-persist test to verify it fails**

Run: `docker compose run --rm api pytest packages/labeling/tests/test_pipeline_classification.py -v`
Expected: FAIL — `_upsert_insight() got an unexpected keyword argument 'desk_category'`

- [ ] **Step 11: Extend `_upsert_insight` and `run()`**

In `backend/packages/labeling/src/labeling/pipeline.py`, add to the imports (after line 13 `from labeling.llm import ...`):

```python
from core.taxonomy import normalize_desk, normalize_user_need
```

Replace the `_upsert_insight` signature and body (lines 188-212) with:

```python
async def _upsert_insight(
    session: AsyncSession,
    cluster_id: uuid.UUID,
    what_happened: str | None,
    parties_involved: list[str] | None,
    editorial_angle: str | None,
    summary: list[str] | None = None,
    desk_category: str | None = None,
    user_need_category: str | None = None,
) -> None:
    """Non-destructive: only overwrites a field when the new value is non-None."""
    insight = (
        await session.execute(
            select(ClusterInsight).where(ClusterInsight.cluster_id == cluster_id)
        )
    ).scalar_one_or_none()
    if insight is None:
        insight = ClusterInsight(cluster_id=cluster_id)
        session.add(insight)
    if what_happened is not None:
        insight.what_happened = what_happened
    if parties_involved is not None:
        insight.parties_involved = parties_involved
    if editorial_angle is not None:
        insight.editorial_angle = editorial_angle
    if summary is not None:
        insight.summary = summary
    if desk_category is not None:
        insight.desk_category = desk_category
    if user_need_category is not None:
        insight.user_need_category = user_need_category
```

Then in `run()`, replace the `_upsert_insight(...)` call (lines 299-306) with:

```python
            await _upsert_insight(
                session,
                cluster_id,
                result.get("what_happened"),
                result.get("parties_involved"),
                result.get("editorial_angle"),
                result.get("summary"),
                desk_category=normalize_desk(result.get("desk_category")),
                user_need_category=normalize_user_need(result.get("user_need_category")),
            )
```

(The fallback `result` dicts at lines ~250 and ~286 omit the two keys; `result.get(...)` returns `None` for them, so `normalize_*` yields `None` and the fields are left unset — no edit needed there.)

- [ ] **Step 12: Run pipeline-persist test to verify it passes**

Run: `docker compose run --rm api pytest packages/labeling/tests/test_pipeline_classification.py -v`
Expected: PASS (2 passed)

- [ ] **Step 13: Run the full labeling suite for regressions**

Run: `docker compose run --rm api pytest packages/labeling/tests/ -v`
Expected: PASS (no regressions in `test_llm.py`, `test_pipeline_integration.py`, etc.)

- [ ] **Step 14: Commit**

```bash
git add packages/labeling/src/labeling/schemas.py packages/labeling/src/labeling/prompts.py packages/labeling/src/labeling/pipeline.py packages/labeling/tests/
git commit -m "feat(labeling): classify cluster desk + user-need via API LLM call"
```

---

## Task 5: Labeling — local (Gemma) path parity

**Files:**
- Modify: `backend/packages/labeling/src/labeling/prompts.py` (`_CLUSTER_INSIGHT_USER`, lines 50-66)
- Modify: `backend/packages/labeling/src/labeling/llm.py` (`_FIELD_RE` line 91-99, `_parse_cluster_insight` line 113-147)
- Test: `backend/packages/labeling/tests/test_llm.py`

**Interfaces:**
- Consumes: `_DESK_OPTIONS`, `_USER_NEED_OPTIONS` from `prompts.py` (Task 4 Step 7).
- Produces: local `_parse_cluster_insight` returns a dict that also contains `desk_category` and `user_need_category` keys.

- [ ] **Step 1: Write the failing parser test**

Append to `backend/packages/labeling/tests/test_llm.py`:

```python
def test_parse_cluster_insight_extracts_desk_and_user_need() -> None:
    from labeling.llm import _parse_cluster_insight

    raw = (
        "LABEL: Sidang korupsi pejabat daerah\n"
        "APA_TERJADI: Terdakwa hadir di pengadilan.\n"
        "SUDUT: Telusuri aliran dana.\n"
        "PIHAK: KPK\n"
        "KLAIM: Dana mengalir ke proyek fiktif.\n"
        "DESK: Hukum\n"
        "KEBUTUHAN: Update me\n"
    )
    result = _parse_cluster_insight(raw)
    assert result["desk_category"] == "Hukum"
    assert result["user_need_category"] == "Update me"


def test_parse_cluster_insight_missing_classification_is_none() -> None:
    from labeling.llm import _parse_cluster_insight

    raw = "LABEL: Topik tanpa klasifikasi\n"
    result = _parse_cluster_insight(raw)
    assert result["desk_category"] is None
    assert result["user_need_category"] is None
```

- [ ] **Step 2: Run parser test to verify it fails**

Run: `docker compose run --rm api pytest packages/labeling/tests/test_llm.py::test_parse_cluster_insight_extracts_desk_and_user_need -v`
Expected: FAIL — `KeyError: 'desk_category'`

- [ ] **Step 3: Extend the regex and parser**

In `backend/packages/labeling/src/labeling/llm.py`, replace `_FIELD_RE` (lines 91-99) with:

```python
_FIELD_RE = re.compile(
    r"^[\s\d.\-•]*"
    r"(?:\*+)?"
    r"(?P<key>LABEL|APA_TERJADI|APA\s+TERJADI|SUDUT|PIHAK|KLAIM|DESK|KEBUTUHAN)"
    r"(?:\*+)?"
    r"\s*:\s*"
    r"(?P<value>.*)",
    re.IGNORECASE,
)
```

Replace `_parse_cluster_insight` (lines 113-147) with:

```python
def _parse_cluster_insight(raw: str) -> dict[str, Any]:
    label: str | None = None
    what_happened_parts: list[str] = []
    parties: list[str] = []
    editorial_angle: str | None = None
    summary: list[str] = []
    desk_category: str | None = None
    user_need_category: str | None = None

    for raw_line in raw.splitlines():
        m = _FIELD_RE.match(raw_line.strip())
        if not m:
            continue
        key = re.sub(r"\s+", "_", m.group("key").upper())
        value = m.group("value").strip().strip("*").strip()
        if not value:
            continue

        if key == "LABEL" and label is None:
            label = _strip_label(value)
        elif key == "APA_TERJADI":
            what_happened_parts.append(value)
        elif key == "SUDUT" and editorial_angle is None:
            editorial_angle = value
        elif key == "PIHAK":
            if value.lower() not in _PIHAK_NONE_MARKERS:
                parties.append(value)
        elif key == "KLAIM":
            summary.append(value)
        elif key == "DESK" and desk_category is None:
            desk_category = value
        elif key == "KEBUTUHAN" and user_need_category is None:
            user_need_category = value

    return {
        "label": label,
        "what_happened": " ".join(what_happened_parts) or None,
        "parties_involved": parties or None,
        "editorial_angle": editorial_angle,
        "summary": summary or None,
        "desk_category": desk_category,
        "user_need_category": user_need_category,
    }
```

(Coercion to the canonical value happens later in `pipeline.run()` via `normalize_desk` / `normalize_user_need`, so the raw parsed string is fine here.)

- [ ] **Step 4: Extend the local prompt**

In `backend/packages/labeling/src/labeling/prompts.py`, replace `_CLUSTER_INSIGHT_USER` (lines 50-66) with:

```python
_CLUSTER_INSIGHT_USER = (
    "{system_prompt}\n\n"
    "Berikut {count} sudut liputan berbeda dari satu klaster berita yang sama:\n\n"
    "{articles}\n\n"
    "Hasilkan TUJUH bagian. Ikuti format persis seperti contoh, "
    "satu baris per prefix. Jangan tambah komentar lain.\n\n"
    "LABEL: <topik 5 sampai 7 kata tanpa tanda baca>\n"
    "APA_TERJADI: <1 sampai 2 kalimat menjelaskan kejadian inti>\n"
    "SUDUT: <1 kalimat angle editorial yang relevan untuk redaksi>\n"
    "PIHAK: <nama pihak atau tokoh utama>\n"
    "PIHAK: <pihak lain jika ada>\n"
    "KLAIM: <fakta penting 1>\n"
    "KLAIM: <fakta penting 2>\n"
    "DESK: <pilih satu dari: " + _DESK_OPTIONS + ">\n"
    "KEBUTUHAN: <pilih satu dari: " + _USER_NEED_OPTIONS + ">\n\n"
    "Tulis PIHAK satu nama per baris, maksimal 5 baris. "
    "Tulis KLAIM satu kalimat per baris, maksimal 7 baris. "
    "Kalau tidak yakin pihak, tulis 'PIHAK: tidak disebutkan' sekali saja."
)
```

- [ ] **Step 5: Run parser + prompt tests to verify they pass**

Run: `docker compose run --rm api pytest packages/labeling/tests/test_llm.py packages/labeling/tests/test_prompts.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/labeling/src/labeling/llm.py packages/labeling/src/labeling/prompts.py packages/labeling/tests/test_llm.py
git commit -m "feat(labeling): local Gemma path emits desk + user-need fields"
```

---

## Task 6: API — expose fields & hard-filter `/morning`

**Files:**
- Modify: `backend/packages/api/src/api/routes/clusters.py` (`ClusterSummary` line 28-51, `_to_summary` line 128-155, `morning_clusters` line 297-319)
- Test: `backend/packages/api/tests/test_clusters.py` (helper line 38-87, new tests)

**Interfaces:**
- Consumes: `settings.morning_allowed_desks`, `settings.morning_denied_user_needs` (Task 2); `ClusterInsight.desk_category` / `.user_need_category` (Task 3).
- Produces: `ClusterSummary.desk_category: str | None`, `ClusterSummary.user_need_category: str | None` in API responses.

- [ ] **Step 1: Update the test helper defaults (so existing morning tests keep passing)**

In `backend/packages/api/tests/test_clusters.py`, in `_cluster_with_insight`, add two parameters to the signature (after `parent_cluster_id: uuid.UUID | None = None,` at line 60):

```python
    desk_category: str = "Politik",
    user_need_category: str = "Update me",
```

and pass them into the `ClusterInsight(...)` constructor (after `summary=summary,` at line 85):

```python
        desk_category=desk_category,
        user_need_category=user_need_category,
```

- [ ] **Step 2: Write the failing exclusion tests**

Append to `backend/packages/api/tests/test_clusters.py`:

```python
async def test_morning_excludes_off_desk_cluster(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(run.id, desk_category="Hiburan")
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert str(cluster.id) not in ids


async def test_morning_excludes_denied_user_need(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(run.id, user_need_category="Divert me")
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert str(cluster.id) not in ids


async def test_morning_excludes_null_classification(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(
        run.id, desk_category=None, user_need_category=None
    )
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["clusters"]]
    assert str(cluster.id) not in ids


async def test_morning_exposes_classification_fields(
    session: AsyncSession, client: AsyncClient
) -> None:
    run = ClusterRun(id=uuid.uuid4(), finished_at=_NOW)
    cluster, insight = _cluster_with_insight(
        run.id, desk_category="Hukum", user_need_category="Educate me"
    )
    session.add_all([run, cluster, insight])
    await session.flush()

    response = await client.get("/api/v1/clusters/morning")
    rows = {r["id"]: r for r in response.json()["clusters"]}
    assert rows[str(cluster.id)]["desk_category"] == "Hukum"
    assert rows[str(cluster.id)]["user_need_category"] == "Educate me"
```

Note: `_cluster_with_insight(run.id, desk_category=None, ...)` requires the signature default to accept `None`; the type hint `str` still accepts `None` at runtime in Python, and the column is nullable, so this works.

- [ ] **Step 3: Run the exclusion tests to verify they fail**

Run: `docker compose run --rm api pytest packages/api/tests/test_clusters.py -k "off_desk or denied_user_need or null_classification or exposes_classification" -v`
Expected: FAIL — off-desk/denied/null clusters still appear; classification fields absent from response (KeyError / wrong value).

- [ ] **Step 4: Add fields to `ClusterSummary`**

In `backend/packages/api/src/api/routes/clusters.py`, in `class ClusterSummary`, after `editorial_quadrant: str | None` (line 46), insert:

```python
    desk_category: str | None
    user_need_category: str | None
```

- [ ] **Step 5: Populate fields in `_to_summary`**

In `_to_summary`, after `editorial_quadrant=insight.editorial_quadrant if insight else None,` (line 149), insert:

```python
        desk_category=insight.desk_category if insight else None,
        user_need_category=insight.user_need_category if insight else None,
```

- [ ] **Step 6: Add the hard filter to `morning_clusters`**

In `morning_clusters`, replace the `.where(...)` block (lines 303-307) with:

```python
        .where(
            run_filter,
            ClusterInsight.tempo_covered.is_(False),
            ClusterInsight.desk_category.in_(settings.morning_allowed_desks),
            ClusterInsight.user_need_category.notin_(settings.morning_denied_user_needs),
            _leaf_guard(),
        )
```

(`.in_([])` / `.notin_([])` are handled safely by SQLAlchemy: an empty allow-list excludes everything; an empty deny-list excludes nothing. `desk_category IN (...)` drops NULL desks; `user_need_category NOT IN (...)` drops NULL needs — both intended.)

- [ ] **Step 7: Run the new tests to verify they pass**

Run: `docker compose run --rm api pytest packages/api/tests/test_clusters.py -k "off_desk or denied_user_need or null_classification or exposes_classification" -v`
Expected: PASS (4 passed)

- [ ] **Step 8: Run the full cluster suite for regressions**

Run: `docker compose run --rm api pytest packages/api/tests/test_clusters.py packages/api/tests/test_clusters_no_gsc_leak.py -v`
Expected: PASS (the existing morning include/ordering/top_n tests still pass because the helper now defaults to an allowed desk + need).

- [ ] **Step 9: Commit**

```bash
git add packages/api/src/api/routes/clusters.py packages/api/tests/test_clusters.py
git commit -m "feat(api): hard-filter /morning by desk + user-need, expose classification"
```

---

## Task 7: Documentation mirrors

**Files:**
- Modify: `docs/schema.dbml` (cluster_insight table, after `editorial_angle`)
- Modify: `backend/.env.example`
- Modify: `CLAUDE.md` (morning endpoint note)

**Interfaces:** none (docs only).

- [ ] **Step 1: Update `docs/schema.dbml`**

In `docs/schema.dbml`, inside `Table cluster_insight`, after the `editorial_angle text  // ...` line, insert:

```
  desk_category text  // LLM-assigned desk (labeling step); /morning hard-filters on morning_allowed_desks
  user_need_category text  // LLM-assigned reader need (labeling step); /morning rejects morning_denied_user_needs
```

- [ ] **Step 2: Update `backend/.env.example`**

Append to `backend/.env.example`:

```
# Morning Tempo-relevance filter (read-time policy; JSON arrays).
# Defaults live in core/config.py; override only to retune editorial scope.
# MORNING_ALLOWED_DESKS=["Politik","Hukum","Nasional","Ekonomi & Bisnis","Internasional","Investigasi","Sains & Teknologi","Lingkungan"]
# MORNING_DENIED_USER_NEEDS=["Divert me","Keep me engaged"]
```

- [ ] **Step 3: Update the `/morning` summary in `CLAUDE.md`**

In `CLAUDE.md`, in the "API endpoints" section, the morning endpoint is part of the live read list. Update the route's docstring summary in code is already covered by Task 6; in `CLAUDE.md` add a clause to the API endpoints paragraph after listing `/api/v1/clusters/morning`:

Find the sentence listing live read endpoints and append after it:

```
`/clusters/morning` additionally hard-filters to clusters whose `desk_category` is in `morning_allowed_desks` AND whose `user_need_category` is not in `morning_denied_user_needs` (classification written by the labeling step).
```

- [ ] **Step 4: Commit**

```bash
git add docs/schema.dbml backend/.env.example CLAUDE.md
git commit -m "docs: mirror desk + user-need classification and /morning filter"
```

---

## Post-implementation: deploy / backfill step (operator action, not code)

After deploying and running `alembic upgrade head` against the production DB, existing
`cluster_insight` rows have NULL `desk_category` → `/morning` is empty until the next
labeling run. Re-label the current run in place so morning is populated immediately:

```bash
docker compose --profile manual run --rm pipeline label
```

Verify `/api/v1/clusters/morning` returns clusters and that each has non-null
`desk_category` / `user_need_category`. Record this in the deploy checklist
(`docs/operations-sop.md` if a checklist section exists).

---

## Self-Review

**Spec coverage:**
- §1 data model → Task 3. §2 taxonomy → Task 1. §2 config policy → Task 2. §3 labeling LLM (API) → Task 4. §3 labeling LLM (local parity) → Task 5. §4 `/morning` WHERE → Task 6. §5 API fields → Task 6. §6 pipeline interaction/non-destructive upsert → Task 4 (verified by `test_upsert_insight_*`). §7 deploy/backfill → Post-implementation section. §8 testing → Tasks 1,2,4,5,6. §9 out-of-scope (/deferred, analyst de-dup, other endpoints) → respected; not touched.
- Gap check: existing morning tests would break under the new filter — covered by Task 6 Step 1 (helper defaults). No remaining gaps.

**Placeholder scan:** No TBD/TODO; every code step shows full code; every command has expected output.

**Type consistency:** `desk_category` / `user_need_category` are `str | None` across model (Task 3), schema (Task 4), `_upsert_insight` kwargs (Task 4), `ClusterSummary` + `_to_summary` (Task 6). `normalize_desk` / `normalize_user_need` signatures `(str | None) -> str | None` used consistently in Task 1 and Task 4 Step 11. `DESK_CATEGORIES` / `USER_NEED_CATEGORIES` are `tuple[str, ...]`, joined to strings in prompts (Task 4/5). Config lists are `list[str]`, consumed by `.in_()` / `.notin_()` (Task 6).
