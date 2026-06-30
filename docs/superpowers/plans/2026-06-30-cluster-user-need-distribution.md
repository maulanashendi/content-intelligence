# Cluster User-Need Distribution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a grounded per-cluster user-need distribution (over the 8 News-Needs categories) in `cluster_insight`, expose it via the cluster API, and visualize it as a radar + bars on the cluster detail view.

**Architecture:** The existing single insight LLM call (one per cluster) is extended to tag each representative article with up to 2 needs. A pure function counts those tags into an 8-key distribution; the argmax becomes the dominant need (kept on the existing `user_need_category`, which still drives `/morning`). The distribution and sample size are persisted and surfaced read-only. Frontend promotes the existing analyst radar/bars to `@ei-fe/ui` and renders them on cluster detail via a feature-local adapter.

**Tech Stack:** Python 3.11, SQLAlchemy 2 (async), Alembic, Pydantic v2, FastAPI; React + TypeScript, Zod, TanStack Query, Vite, Bun (frontend tests).

**Spec:** `docs/superpowers/specs/2026-06-30-cluster-user-need-distribution-design.md`

## Global Constraints

- **Branch/isolation:** work only in this worktree (`feat+cluster-user-need-distribution`, off `master` @ `5f6a1e0`). A live session is editing `api/routes/clusters.py` + `docs/decisions.md` on `feat/morning-dna-toggle` — our edits there must stay additive (response-model fields + `_to_summary` mapping only); do NOT touch the `/morning` where-clause or add a `dna` param.
- **Taxonomy single source:** need strings come only from `core.taxonomy` (`USER_NEED_CATEGORIES`, `normalize_user_need`). No second hardcoded copy in `labeling`.
- **`api` purity:** no torch/ML imports in `api`. No `print()` anywhere — JSON logging only. src layout per package.
- **No cost regression:** exactly one LLM call per cluster in the labeling step.
- **Non-destructive upsert:** `_upsert_insight` only overwrites a field when the new value is non-`None`.
- **API contract:** any endpoint signature change updates the Pydantic model + `response_model=` + one-line route `summary` in the same commit; `/openapi.json` is the contract (CLAUDE.md).
- **Frontend layering:** promoted components live in `@ei-fe/ui` (Tailwind + tokens + ui primitives only — no legacy `.card`/`.kw-row` on NEW components). No cross-feature imports; adapters stay in their own feature.
- **8-key distribution invariant:** when non-`null`, `user_need_distribution` has exactly the 8 `USER_NEED_CATEGORIES` keys (zeros included); sum of values == total valid tags.
- **Dominant consistency:** when set from a non-`null` distribution, `user_need_category` == argmax of `user_need_distribution`, tie-broken by `USER_NEED_CATEGORIES` order.

## Setup & verification commands

Run once in the worktree before starting:

```bash
cd backend && uv sync --all-packages        # host venv for unit tests (memory: --all-packages, not --package)
```

- **Backend unit tests (no DB)** — host: `cd backend && ./.venv/bin/python -m pytest packages/<mod>/tests/<file> -q`
- **Backend DB-backed tests** — Docker (canonical): `cd backend && docker compose up -d postgres && docker compose run --rm api pytest packages/<mod>/tests/<file> -q`
  - ⚠️ **Parallel-stack caveat:** the live `feat/morning-dna-toggle` stack may already bind host ports 5432/8000. This worktree is a separate compose project (different dir). If `up` fails on a port clash, either stop the other stack's `postgres`/`api` or run these DB tests when it is down. Tests use the compose `postgres`, not the host.
- **Migrations** — `cd backend && docker compose run --rm api alembic revision --autogenerate -m "..."` then `docker compose run --rm api alembic upgrade head`.
- **Frontend tests** — `cd frontend && bun test packages/<pkg>/tests/<file>`
- **Frontend build check** — `cd frontend && bun run --filter @ei-fe/app vite build --outDir /tmp/ei-build-check` (memory: `tsc -b` falsely fails on root-owned stale `dist`; do NOT use it to judge).

---

## Task 1: Schema columns + migration (`core`)

**Files:**
- Modify: `backend/packages/core/src/core/models.py` (`ClusterInsight`, after the `user_need_category` column ~L428)
- Modify: `docs/schema.dbml` (`cluster_insight` table)
- Create: `backend/alembic/versions/<autogen>_add_cluster_user_need_distribution.py`
- Test: `backend/packages/core/tests/test_cluster_insight_columns.py` (new)

**Interfaces:**
- Produces: `ClusterInsight.user_need_distribution: Mapped[dict[str, int] | None]`, `ClusterInsight.user_need_reps_tagged: Mapped[int | None]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/packages/core/tests/test_cluster_insight_columns.py
import uuid

from core.models import ClusterInsight


def test_cluster_insight_accepts_user_need_distribution_fields() -> None:
    ci = ClusterInsight(
        cluster_id=uuid.uuid4(),
        user_need_distribution={"Update me": 2, "Educate me": 1},
        user_need_reps_tagged=3,
    )
    assert ci.user_need_distribution == {"Update me": 2, "Educate me": 1}
    assert ci.user_need_reps_tagged == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest packages/core/tests/test_cluster_insight_columns.py -q`
Expected: FAIL — `TypeError: 'user_need_distribution' is an invalid keyword argument for ClusterInsight`.

- [ ] **Step 3: Add the columns**

In `models.py`, `JSONB` is already imported (`from sqlalchemy.dialects.postgresql import JSONB, UUID`). Add directly after the `user_need_category` line:

```python
    user_need_category: Mapped[str | None] = mapped_column(String)
    user_need_distribution: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    user_need_reps_tagged: Mapped[int | None] = mapped_column(Integer)
```

In `docs/schema.dbml`, add to the `cluster_insight` table near `user_need_category`:

```
  user_need_distribution jsonb
  user_need_reps_tagged integer
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest packages/core/tests/test_cluster_insight_columns.py -q`
Expected: PASS.

- [ ] **Step 5: Generate and apply the migration**

```bash
cd backend
docker compose up -d postgres
docker compose run --rm api alembic upgrade head        # baseline to current head
docker compose run --rm api alembic revision --autogenerate -m "add cluster user_need distribution"
```

Open the new file in `backend/alembic/versions/`. Verify `upgrade()` contains exactly two `op.add_column('cluster_insight', ...)` for `user_need_distribution` (JSONB) and `user_need_reps_tagged` (Integer), and `downgrade()` drops both. Remove any unrelated autogen noise. Then:

```bash
docker compose run --rm api alembic upgrade head
```

Expected: applies cleanly, no errors.

- [ ] **Step 6: Commit**

```bash
git add backend/packages/core/src/core/models.py docs/schema.dbml \
        backend/packages/core/tests/test_cluster_insight_columns.py \
        backend/alembic/versions/*add_cluster_user_need_distribution*.py
git commit -m "feat(core): cluster_insight user-need distribution columns"
```

---

## Task 2: `aggregate_user_needs` pure function (`labeling`)

**Files:**
- Modify: `backend/packages/labeling/src/labeling/pipeline.py` (add function + module constant near the top, after the existing `from core.taxonomy import ...` import — extend it to also import `USER_NEED_CATEGORIES`)
- Test: `backend/packages/labeling/tests/test_aggregate_user_needs.py` (new)

**Interfaces:**
- Produces: `aggregate_user_needs(article_needs: list[list[str]] | None) -> tuple[dict[str, int] | None, str | None, int]` returning `(distribution_over_8_needs, dominant_need, reps_tagged)`; `(None, None, 0)` when there are no valid tags.

- [ ] **Step 1: Write the failing test**

```python
# backend/packages/labeling/tests/test_aggregate_user_needs.py
from core.taxonomy import USER_NEED_CATEGORIES
from labeling.pipeline import aggregate_user_needs


def test_empty_or_none_returns_nulls() -> None:
    assert aggregate_user_needs(None) == (None, None, 0)
    assert aggregate_user_needs([]) == (None, None, 0)
    assert aggregate_user_needs([[], []]) == (None, None, 0)


def test_counts_frequency_over_eight_keys() -> None:
    dist, dominant, reps = aggregate_user_needs(
        [["Update me", "Give me perspective"], ["Update me"], ["Educate me"]]
    )
    assert set(dist) == set(USER_NEED_CATEGORIES)
    assert dist["Update me"] == 2
    assert dist["Give me perspective"] == 1
    assert dist["Educate me"] == 1
    assert dist["Divert me"] == 0
    assert dominant == "Update me"
    assert reps == 3


def test_normalizes_and_drops_unknown() -> None:
    dist, dominant, reps = aggregate_user_needs([["update me", "Garbage need"], ["???"]])
    assert dist["Update me"] == 1   # casefold-normalized
    assert dominant == "Update me"
    assert reps == 1                # second article contributed nothing


def test_dedupes_and_caps_at_two_per_article() -> None:
    dist, _, reps = aggregate_user_needs([["Update me", "Update me", "Educate me", "Divert me"]])
    assert dist["Update me"] == 1        # de-duped within the article
    assert dist["Educate me"] == 1
    assert dist["Divert me"] == 0        # capped at 2 distinct needs
    assert reps == 1


def test_dominant_tie_break_follows_taxonomy_order() -> None:
    # "Update me" and "Educate me" both count 1; "Update me" precedes in USER_NEED_CATEGORIES.
    _, dominant, _ = aggregate_user_needs([["Educate me"], ["Update me"]])
    assert dominant == "Update me"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_aggregate_user_needs.py -q`
Expected: FAIL — `ImportError: cannot import name 'aggregate_user_needs'`.

- [ ] **Step 3: Implement the function**

In `pipeline.py`, change the taxonomy import and add the function (place it just below the imports):

```python
from core.taxonomy import USER_NEED_CATEGORIES, normalize_desk, normalize_user_need

_MAX_NEEDS_PER_ARTICLE = 2


def aggregate_user_needs(
    article_needs: list[list[str]] | None,
) -> tuple[dict[str, int] | None, str | None, int]:
    if not article_needs:
        return None, None, 0
    distribution = {need: 0 for need in USER_NEED_CATEGORIES}
    reps_tagged = 0
    for raw_needs in article_needs:
        valid: list[str] = []
        for raw in raw_needs or []:
            norm = normalize_user_need(raw)
            if norm is not None and norm not in valid:
                valid.append(norm)
            if len(valid) == _MAX_NEEDS_PER_ARTICLE:
                break
        for norm in valid:
            distribution[norm] += 1
        if valid:
            reps_tagged += 1
    if reps_tagged == 0:
        return None, None, 0
    dominant = max(USER_NEED_CATEGORIES, key=lambda need: distribution[need])
    return distribution, dominant, reps_tagged
```

(`max` over the ordered tuple returns the first maximum → taxonomy-order tie-break.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_aggregate_user_needs.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/packages/labeling/src/labeling/pipeline.py \
        backend/packages/labeling/tests/test_aggregate_user_needs.py
git commit -m "feat(labeling): aggregate_user_needs counts per-article tags into a distribution"
```

---

## Task 3: LLM schema + prompt for per-rep tags (`labeling`)

**Files:**
- Modify: `backend/packages/labeling/src/labeling/schemas.py` (`ClusterInsightLLM`)
- Modify: `backend/packages/labeling/src/labeling/prompts.py` (`_CLUSTER_INSIGHT_USER_API`)
- Modify: `backend/packages/labeling/tests/test_schemas.py` (the two key-set assertions break — update them)
- Modify: `backend/packages/labeling/tests/test_prompts.py` (add per-article-needs assertion)

**Interfaces:**
- Produces: `ClusterInsightLLM.article_needs: list[list[str]] | None` — one inner list (≤2 needs) per representative, in prompt order. `result.get("article_needs")` is what Task 4 feeds to `aggregate_user_needs`.

- [ ] **Step 1: Update the failing tests first (TDD: define new contract)**

In `test_schemas.py`, edit `test_cluster_insight_parses_full_payload` to add `"article_needs"` to the input and the expected key set:

```python
        {
            "label": "Kenaikan harga beras premium",
            "what_happened": "Harga beras melonjak di sejumlah daerah.",
            "parties_involved": ["Bulog", "Kemendag"],
            "editorial_angle": "Telusuri rantai distribusi.",
            "summary": ["Harga naik 10 persen", "Stok menipis"],
            "desk_category": "Ekonomi & Bisnis",
            "user_need_category": "Update me",
            "article_needs": [["Update me", "Give me perspective"], ["Update me"]],
        }
    )
    d = m.model_dump()
    assert d["label"] == "Kenaikan harga beras premium"
    assert d["parties_involved"] == ["Bulog", "Kemendag"]
    assert d["desk_category"] == "Ekonomi & Bisnis"
    assert d["user_need_category"] == "Update me"
    assert d["article_needs"] == [["Update me", "Give me perspective"], ["Update me"]]
    assert set(d) == {
        "label", "what_happened", "parties_involved", "editorial_angle",
        "summary", "desk_category", "user_need_category", "article_needs",
    }
```

And in `test_cluster_insight_minimal`, add `"article_needs": None` to the expected dict:

```python
    assert m.model_dump() == {
        "label": "X",
        "what_happened": None,
        "parties_involved": None,
        "editorial_angle": None,
        "summary": None,
        "desk_category": None,
        "user_need_category": None,
        "article_needs": None,
    }
```

In `test_prompts.py`, add:

```python
def test_cluster_insight_api_prompt_requests_per_article_needs() -> None:
    msgs = format_cluster_insight_messages_api(
        [{"title": "Sidang korupsi", "first_paragraph": "Terdakwa hadir."}]
    )
    body = msgs[0]["content"]
    assert "article_needs" in body
    assert "paling banyak 2" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_schemas.py packages/labeling/tests/test_prompts.py -q`
Expected: FAIL — schema dump missing `article_needs`; prompt body missing the new text.

- [ ] **Step 3: Add the schema field**

In `schemas.py`, `ClusterInsightLLM`, append:

```python
    article_needs: list[list[str]] | None = None
```

- [ ] **Step 4: Extend the API prompt**

In `prompts.py`, in `_CLUSTER_INSIGHT_USER_API`, append after the `user_need_category` sentence (before the closing of the string):

```python
    "Terakhir, untuk SETIAP sudut liputan di atas (sesuai urutan), tentukan article_needs: "
    "sebuah daftar berisi paling banyak 2 kebutuhan pembaca dari: " + _USER_NEED_OPTIONS + ". "
    "Kembalikan article_needs sebagai list-of-list, satu sublist per sudut sesuai urutannya."
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ./.venv/bin/python -m pytest packages/labeling/tests/test_schemas.py packages/labeling/tests/test_prompts.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/packages/labeling/src/labeling/schemas.py \
        backend/packages/labeling/src/labeling/prompts.py \
        backend/packages/labeling/tests/test_schemas.py \
        backend/packages/labeling/tests/test_prompts.py
git commit -m "feat(labeling): per-article user-need tags in insight schema + prompt"
```

---

## Task 4: Pipeline persistence wiring (`labeling`)

**Files:**
- Modify: `backend/packages/labeling/src/labeling/pipeline.py` (`_upsert_insight` signature + body; `run()` aggregation glue ~L306)
- Test: `backend/packages/labeling/tests/test_pipeline_classification.py` (extend `_upsert_insight` coverage)
- Test: `backend/packages/labeling/tests/test_pipeline_integration.py` (add a run() wiring test)

**Interfaces:**
- Consumes: `aggregate_user_needs` (Task 2), `result["article_needs"]` (Task 3), `ClusterInsight.user_need_distribution` / `user_need_reps_tagged` (Task 1).
- Produces: `_upsert_insight(..., user_need_distribution: dict[str, int] | None = None, user_need_reps_tagged: int | None = None)`.

- [ ] **Step 1: Write the failing tests**

Add to `test_pipeline_classification.py`:

```python
async def test_upsert_insight_persists_distribution(clean_db) -> None:
    async with get_session() as session:
        run = ClusterRun(id=uuid.uuid4())
        cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, is_current=True)
        session.add_all([run, cluster])
        await session.flush()

        await _upsert_insight(
            session, cluster.id, None, None, None, None,
            desk_category="Politik", user_need_category="Update me",
            user_need_distribution={"Update me": 2, "Educate me": 1},
            user_need_reps_tagged=3,
        )
        await session.commit()

        row = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one()
        assert row.user_need_distribution == {"Update me": 2, "Educate me": 1}
        assert row.user_need_reps_tagged == 3


async def test_upsert_insight_none_distribution_does_not_overwrite(clean_db) -> None:
    async with get_session() as session:
        run = ClusterRun(id=uuid.uuid4())
        cluster = ArticleCluster(id=uuid.uuid4(), run_id=run.id, is_current=True)
        session.add_all([run, cluster])
        await session.flush()

        await _upsert_insight(
            session, cluster.id, None, None, None, None,
            user_need_distribution={"Update me": 1}, user_need_reps_tagged=1,
        )
        await session.commit()
        await _upsert_insight(
            session, cluster.id, None, None, None, None,
            user_need_distribution=None, user_need_reps_tagged=None,
        )
        await session.commit()

        row = (
            await session.execute(
                select(ClusterInsight).where(ClusterInsight.cluster_id == cluster.id)
            )
        ).scalar_one()
        assert row.user_need_distribution == {"Update me": 1}
        assert row.user_need_reps_tagged == 1
```

Add to `test_pipeline_integration.py` (self-contained fake; mirrors `test_run_writes_labels_and_insight_to_leaf_clusters` seeding):

```python
@pytest.mark.asyncio
async def test_run_writes_user_need_distribution(clean_db, monkeypatch):
    source = _source()
    run_row = ClusterRun(id=uuid.uuid4())
    async with get_session() as session:
        session.add_all([source, run_row])
        await session.flush()
        cluster = ArticleCluster(id=uuid.uuid4(), run_id=run_row.id, is_current=True, member_count=2)
        session.add(cluster)
        await session.flush()
        for j in range(2):
            article = _article(source.id, f"Artikel {j}")
            session.add(article)
            await session.flush()
            session.add(
                ArticleClusterMember(cluster_id=cluster.id, article_id=article.id, relevance_score=1.0)
            )
        await session.commit()

    async def fake(_reps):
        return {
            "label": "Topik uji",
            "what_happened": "Sesuatu terjadi.",
            "parties_involved": ["A", "B"],
            "editorial_angle": "Sudut.",
            "summary": ["x"],
            "desk_category": "Politik",
            "user_need_category": None,
            "article_needs": [["Update me", "Give me perspective"], ["Update me"]],
        }

    monkeypatch.setattr("labeling.pipeline.generate_cluster_insight", fake)

    await run()

    async with get_session() as session:
        row = (await session.execute(select(ClusterInsight))).scalars().one()
    assert row.user_need_distribution["Update me"] == 2
    assert row.user_need_reps_tagged == 2
    assert row.user_need_category == "Update me"   # dominant, not the (None) holistic field
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && docker compose run --rm api pytest packages/labeling/tests/test_pipeline_classification.py packages/labeling/tests/test_pipeline_integration.py -q`
Expected: FAIL — `_upsert_insight` has no `user_need_distribution` kwarg; integration asserts unmet.

- [ ] **Step 3: Extend `_upsert_insight`**

Update the signature and body:

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
    user_need_distribution: dict[str, int] | None = None,
    user_need_reps_tagged: int | None = None,
) -> None:
    """Non-destructive: only overwrites a field when the new value is non-None."""
    ...
    if user_need_category is not None:
        insight.user_need_category = user_need_category
    if user_need_distribution is not None:
        insight.user_need_distribution = user_need_distribution
    if user_need_reps_tagged is not None:
        insight.user_need_reps_tagged = user_need_reps_tagged
```

- [ ] **Step 4: Wire aggregation into `run()`**

Replace the `_upsert_insight(...)` call in `run()` (currently passing `desk_category` + `user_need_category`) with:

```python
            distribution, dominant, reps_tagged = aggregate_user_needs(
                result.get("article_needs")
            )
            user_need = dominant or normalize_user_need(result.get("user_need_category"))
            await _upsert_insight(
                session,
                cluster_id,
                result.get("what_happened"),
                result.get("parties_involved"),
                result.get("editorial_angle"),
                result.get("summary"),
                desk_category=normalize_desk(result.get("desk_category")),
                user_need_category=user_need,
                user_need_distribution=distribution,
                user_need_reps_tagged=reps_tagged or None,
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && docker compose run --rm api pytest packages/labeling/tests/ -q`
Expected: PASS (whole labeling suite green — confirms no regression in the existing integration tests).

- [ ] **Step 6: Commit**

```bash
git add backend/packages/labeling/src/labeling/pipeline.py \
        backend/packages/labeling/tests/test_pipeline_classification.py \
        backend/packages/labeling/tests/test_pipeline_integration.py
git commit -m "feat(labeling): persist user-need distribution + dominant from per-article tags"
```

---

## Task 5: API response fields (`api`)

**Files:**
- Modify: `backend/packages/api/src/api/routes/clusters.py` (`ClusterSummary` model ~L47, `_to_summary` ~L152, route `summary` strings)
- Test: `backend/packages/api/tests/test_clusters.py` (add detail-response assertion)

**Interfaces:**
- Consumes: `ClusterInsight.user_need_distribution`, `ClusterInsight.user_need_reps_tagged` (Task 1).
- Produces: API JSON fields `user_need_distribution: dict[str,int] | None`, `user_need_reps_tagged: int | None` on `ClusterSummary` (inherited by `ClusterDetail`).

⚠️ Keep edits additive and away from the `/morning` where-clause (parallel branch owns that).

- [ ] **Step 1: Write the failing test**

Add to `test_clusters.py` (follow the file's existing cluster-detail seeding helper; if a helper seeds a `ClusterInsight`, set the two fields there). Minimal standalone shape:

```python
async def test_cluster_detail_returns_user_need_distribution(client, clean_db) -> None:
    # Arrange: seed one current leaf cluster + insight with a distribution.
    # (reuse this module's existing seed helper; set:)
    #   insight.user_need_distribution = {"Update me": 2, "Educate me": 1}
    #   insight.user_need_reps_tagged = 3
    # then GET /api/v1/clusters/{id}
    resp = await client.get(f"/api/v1/clusters/{cluster_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_need_distribution"] == {"Update me": 2, "Educate me": 1}
    assert body["user_need_reps_tagged"] == 3
```

(Use the same fixtures/seed pattern already present in `test_clusters.py` for cluster-detail tests; the two new lines on the seeded `ClusterInsight` are the only additions.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && docker compose run --rm api pytest packages/api/tests/test_clusters.py -q -k user_need_distribution`
Expected: FAIL — `KeyError`/missing field (model doesn't expose it yet).

- [ ] **Step 3: Add fields to the Pydantic model**

In `ClusterSummary`, after `user_need_category: str | None`:

```python
    user_need_category: str | None
    user_need_distribution: dict[str, int] | None
    user_need_reps_tagged: int | None
```

- [ ] **Step 4: Map them in `_to_summary`**

After the `user_need_category=...` line in the `ClusterSummary(...)` construction:

```python
        user_need_category=insight.user_need_category if insight else None,
        user_need_distribution=insight.user_need_distribution if insight else None,
        user_need_reps_tagged=insight.user_need_reps_tagged if insight else None,
```

Update the `/clusters/{id}` route `summary=` (and `/morning` if you touch its line — otherwise leave it) to mention "user-need distribution" per the API-contract rule. Do NOT change `response_model` (still `ClusterDetail`/`ClusterListResponse`) or status codes.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && docker compose run --rm api pytest packages/api/tests/test_clusters.py -q`
Expected: PASS (full file green — no regression).

- [ ] **Step 6: Commit**

```bash
git add backend/packages/api/src/api/routes/clusters.py backend/packages/api/tests/test_clusters.py
git commit -m "feat(api): expose user_need_distribution + reps_tagged on cluster responses"
```

---

## Task 6: Promote radar/bars to `@ei-fe/ui` (`frontend`)

**Files:**
- Create: `frontend/packages/ui/src/charts/radar-points.ts`
- Create: `frontend/packages/ui/src/charts/user-needs-radar.tsx` (moved from analyst)
- Create: `frontend/packages/ui/src/charts/user-needs-bars.tsx` (moved from analyst)
- Modify: `frontend/packages/ui/src/index.ts` (export the three)
- Modify: `frontend/packages/features/src/analyst/analyze-result.tsx` (import from `@ei-fe/ui`)
- Modify: `frontend/packages/features/src/analyst/data.ts` (re-export `radarPoints` from `@ei-fe/ui`; remove its local definition)
- Delete: `frontend/packages/features/src/analyst/user-needs-radar.tsx`, `.../user-needs-bars.tsx`
- Test: `frontend/packages/features/tests/analyst-data.test.ts` (unchanged — still imports `radarPoints` from analyst `data.js`; must stay green via re-export)

**Interfaces:**
- Produces: `@ei-fe/ui` exports `UserNeedsRadar`, `UserNeedsBars`, `radarPoints`, and type `UserNeedDatum`.

- [ ] **Step 1: Create `radar-points.ts` in `@ei-fe/ui`**

```ts
// frontend/packages/ui/src/charts/radar-points.ts
export interface UserNeedDatum {
  key: string
  label: string
  value: number
}

export function radarPoints(
  values: number[],
  cx: number,
  cy: number,
  r: number,
): [number, number][] {
  const n = values.length
  return values.map((v, i) => {
    const angle = (-90 + i * (360 / n)) * (Math.PI / 180)
    const radius = (Math.min(100, Math.max(0, v)) / 100) * r
    return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]
  })
}
```

- [ ] **Step 2: Move the components**

Copy `frontend/packages/features/src/analyst/user-needs-radar.tsx` and `user-needs-bars.tsx` into `frontend/packages/ui/src/charts/`. In the radar file, change the import from `import { radarPoints } from "./data.js"` to `import { radarPoints } from "./radar-points.js"` and replace its local `interface Need` with `import type { UserNeedDatum as Need } from "./radar-points.js"`. In the bars file, replace its local `interface Need` the same way. Delete the two originals from the analyst feature.

- [ ] **Step 3: Export from `@ei-fe/ui`**

Append to `frontend/packages/ui/src/index.ts`:

```ts
export { UserNeedsRadar } from "./charts/user-needs-radar.js"
export { UserNeedsBars } from "./charts/user-needs-bars.js"
export { radarPoints } from "./charts/radar-points.js"
export type { UserNeedDatum } from "./charts/radar-points.js"
```

- [ ] **Step 4: Re-point analyst consumers**

In `analyze-result.tsx`, replace the two local imports with:

```ts
import { UserNeedsRadar, UserNeedsBars } from "@ei-fe/ui"
```

In `analyst/data.ts`, delete the local `radarPoints` function and add at the top:

```ts
export { radarPoints } from "@ei-fe/ui"
```

- [ ] **Step 5: Run tests + build to verify**

```bash
cd frontend
bun test packages/features/tests/analyst-data.test.ts
bun run --filter @ei-fe/app vite build --outDir /tmp/ei-build-check
```

Expected: analyst-data tests PASS (radarPoints still importable from analyst `data.js` via re-export); build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/ui/src/charts frontend/packages/ui/src/index.ts \
        frontend/packages/features/src/analyst/analyze-result.tsx \
        frontend/packages/features/src/analyst/data.ts
git add -u frontend/packages/features/src/analyst   # stage the two deletions
git commit -m "refactor(ui): promote UserNeedsRadar/Bars + radarPoints to @ei-fe/ui"
```

---

## Task 7: FE api Zod schema fields (`frontend`)

**Files:**
- Modify: `frontend/packages/api/src/schemas.ts` (`ClusterSummarySchema`)
- Modify: `frontend/packages/api/src/generated.ts` (regenerate, or hand-add the two fields to the `ClusterSummary` block)
- Test: `frontend/packages/api/tests/` (add a parse test, mirroring existing schema tests)

**Interfaces:**
- Consumes: backend API fields (Task 5).
- Produces: `ClusterSummary`/`ClusterDetail` TS types include `user_need_distribution: Record<string, number> | null` and `user_need_reps_tagged: number | null`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/packages/api/tests/cluster-user-need.test.ts
import { describe, test, expect } from "bun:test"
import { ClusterSummarySchema } from "../src/schemas.js"

const base = {
  id: "00000000-0000-0000-0000-000000000001",
  parent_cluster_id: null, label: "x", member_count: 1, is_current: true,
  created_at: "2026-06-30T00:00:00Z", trend_velocity: null, competitor_count: null,
  trend_match_count: null, weighted_trend_score: null, tempo_covered: null,
  last_internal_days_ago: null, underperformed: null, competitor_freshness_days: null,
  demand_score: null, high_demand: null, performance_level: null, editorial_quadrant: null,
  what_happened: null, parties_involved: null, editorial_angle: null,
  bullet_insights: null, insight_calculated_at: null,
}

describe("ClusterSummarySchema user-need distribution", () => {
  test("parses distribution + reps_tagged", () => {
    const out = ClusterSummarySchema.parse({
      ...base,
      user_need_distribution: { "Update me": 2, "Educate me": 1 },
      user_need_reps_tagged: 3,
    })
    expect(out.user_need_distribution).toEqual({ "Update me": 2, "Educate me": 1 })
    expect(out.user_need_reps_tagged).toBe(3)
  })
  test("accepts nulls", () => {
    const out = ClusterSummarySchema.parse({
      ...base, user_need_distribution: null, user_need_reps_tagged: null,
    })
    expect(out.user_need_distribution).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && bun test packages/api/tests/cluster-user-need.test.ts`
Expected: FAIL — Zod strips the unknown keys; `out.user_need_distribution` is `undefined`, not the object.

- [ ] **Step 3: Add fields to the Zod schema**

In `ClusterSummarySchema`, before the closing `})`, add:

```ts
  user_need_distribution: z.record(z.string(), z.number()).nullable(),
  user_need_reps_tagged: z.number().int().nullable(),
```

- [ ] **Step 4: Regenerate `generated.ts`**

With the backend running and migrated:

```bash
cd backend && docker compose up -d api    # serves /openapi.json
cd ../frontend && npx openapi-typescript@7 http://localhost:8000/openapi.json -o packages/api/src/generated.ts
```

If the backend can't be served in this worktree (port clash with the parallel stack), hand-add the two fields to the `ClusterSummary:` block in `generated.ts`:

```ts
            user_need_distribution: { [key: string]: number } | null;
            user_need_reps_tagged: number | null;
```

- [ ] **Step 5: Run test + build to verify**

```bash
cd frontend
bun test packages/api/tests/cluster-user-need.test.ts
bun run --filter @ei-fe/app vite build --outDir /tmp/ei-build-check
```

Expected: PASS; build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/api/src/schemas.ts frontend/packages/api/src/generated.ts \
        frontend/packages/api/tests/cluster-user-need.test.ts
git commit -m "feat(fe-api): user_need_distribution + reps_tagged on cluster schema"
```

---

## Task 8: Cluster-detail user-need card + adapter (`frontend`)

**Files:**
- Create: `frontend/packages/features/src/cluster-detail/user-need-data.ts` (8-axis order + adapter)
- Create: `frontend/packages/features/src/cluster-detail/user-need-card.tsx`
- Modify: `frontend/packages/features/src/cluster-detail/cluster-detail-view.tsx` (render the card)
- Test: `frontend/packages/features/tests/cluster-detail-user-need.test.ts` (adapter)

**Interfaces:**
- Consumes: `ClusterDetail` type (Task 7); `UserNeedsRadar`, `UserNeedsBars`, `UserNeedDatum` from `@ei-fe/ui` (Task 6).
- Produces: `distributionToNeeds(distribution: Record<string, number> | null): UserNeedDatum[]`, `CLUSTER_USER_NEED_ORDER`.

- [ ] **Step 1: Write the failing adapter test**

```ts
// frontend/packages/features/tests/cluster-detail-user-need.test.ts
import { describe, test, expect } from "bun:test"
import { distributionToNeeds, CLUSTER_USER_NEED_ORDER } from "../src/cluster-detail/user-need-data.js"

describe("distributionToNeeds", () => {
  test("returns 8 axes normalized to the peak count", () => {
    const out = distributionToNeeds({ "Update me": 4, "Educate me": 2 })
    expect(out).toHaveLength(8)
    expect(out.map((n) => n.key)).toEqual(CLUSTER_USER_NEED_ORDER.map((n) => n.key))
    expect(out.find((n) => n.key === "Update me")!.value).toBe(100)  // peak
    expect(out.find((n) => n.key === "Educate me")!.value).toBe(50)
    expect(out.find((n) => n.key === "Divert me")!.value).toBe(0)
  })
  test("empty or null distribution → no chart data", () => {
    expect(distributionToNeeds(null)).toEqual([])
    expect(distributionToNeeds({})).toEqual([])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && bun test packages/features/tests/cluster-detail-user-need.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the adapter**

```ts
// frontend/packages/features/src/cluster-detail/user-need-data.ts
import type { UserNeedDatum } from "@ei-fe/ui"

export const CLUSTER_USER_NEED_ORDER = [
  { key: "Update me", label: "Beri tahu" },
  { key: "Keep me engaged", label: "Bikin betah" },
  { key: "Educate me", label: "Edukasi" },
  { key: "Give me perspective", label: "Perspektif" },
  { key: "Inspire me", label: "Inspirasi" },
  { key: "Divert me", label: "Hibur" },
  { key: "Help me", label: "Bantu" },
  { key: "Connect me", label: "Hubungkan" },
] as const

export function distributionToNeeds(
  distribution: Record<string, number> | null,
): UserNeedDatum[] {
  if (!distribution) return []
  const counts = CLUSTER_USER_NEED_ORDER.map((n) => distribution[n.key] ?? 0)
  const max = Math.max(0, ...counts)
  if (max === 0) return []
  return CLUSTER_USER_NEED_ORDER.map((n, i) => ({
    key: n.key,
    label: n.label,
    value: Math.round((counts[i] / max) * 100),
  }))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && bun test packages/features/tests/cluster-detail-user-need.test.ts`
Expected: PASS.

- [ ] **Step 5: Build the card**

```tsx
// frontend/packages/features/src/cluster-detail/user-need-card.tsx
import type { ClusterDetail } from "@ei-fe/api"
import { UserNeedsRadar, UserNeedsBars } from "@ei-fe/ui"
import { distributionToNeeds } from "./user-need-data.js"

export function UserNeedCard({ cluster }: { cluster: ClusterDetail }) {
  const needs = distributionToNeeds(cluster.user_need_distribution)
  const reps = cluster.user_need_reps_tagged ?? 0
  if (needs.length === 0) return null

  return (
    <div
      className="overflow-hidden border rounded-[var(--radius-lg)]"
      style={{ background: "var(--bg-elev)", borderColor: "var(--line)" }}
    >
      <div
        className="flex items-center gap-[10px] px-[14px] py-[12px] border-b"
        style={{ borderColor: "var(--line)" }}
      >
        <span
          className="text-[12px] font-semibold uppercase tracking-[0.01em]"
          style={{ color: "var(--fg-muted)" }}
        >
          Kebutuhan Pembaca
        </span>
        <span
          className="ml-auto text-[11.5px]"
          style={{ color: "var(--fg-faint)", fontFamily: "var(--font-mono)" }}
        >
          {reps < 3 ? "indikatif · " : ""}berdasarkan {reps} artikel
        </span>
      </div>
      <div className="flex flex-col gap-3 p-[14px]">
        <UserNeedsRadar needs={needs} />
        <UserNeedsBars needs={needs} />
      </div>
    </div>
  )
}
```

**Hard-rule compliance (decided up front):** this NEW component must NOT use the legacy `.card`/`.card-head`/`.card-title`/`.card-meta` global classes (CLAUDE.md). It replicates the sibling-card chrome with Tailwind utilities + design tokens only (the JSX above maps 1:1 to `globals.css` `.card`: `bg-elev` background, `var(--line)` border, `var(--radius-lg)` radius, uppercase muted title, mono faint meta).

- [ ] **Step 6: Wire into the detail view**

In `cluster-detail-view.tsx`, add the import and render it in the right column above `RelatedClustersCard`:

```tsx
import { UserNeedCard } from "./user-need-card.js"
```

```tsx
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <UserNeedCard cluster={data} />
          <RelatedClustersCard cluster={data} />
          <FirstReportCard members={data.members} clusterLabel={data.label} />
          <AuditTrailCard cluster={data} />
        </div>
```

- [ ] **Step 7: Verify build + tests**

```bash
cd frontend
bun test packages/features/tests/cluster-detail-user-need.test.ts
bun run --filter @ei-fe/app vite build --outDir /tmp/ei-build-check
```

Expected: PASS; build succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend/packages/features/src/cluster-detail/user-need-data.ts \
        frontend/packages/features/src/cluster-detail/user-need-card.tsx \
        frontend/packages/features/src/cluster-detail/cluster-detail-view.tsx \
        frontend/packages/features/tests/cluster-detail-user-need.test.ts
git commit -m "feat(cluster-detail): user-need distribution radar + bars card"
```

---

## Final verification (after all tasks)

```bash
# Backend — full suites touched
cd backend && docker compose run --rm api pytest packages/core/tests packages/labeling/tests packages/api/tests -q
# Frontend — touched packages + build
cd ../frontend && bun test packages/api packages/features && bun run --filter @ei-fe/app vite build --outDir /tmp/ei-build-check
```

Then add a one-line decision to `docs/decisions.md` (D-number after the latest) recording: "user_need is now a per-cluster distribution insight (counted from per-article tags); dominant retained on `user_need_category` for the unchanged `/morning` gate." Expect an append conflict with `feat/morning-dna-toggle` at merge — resolve by keeping both decisions.

## Self-review (completed during planning)

- **Spec coverage:** schema (T1) · aggregation (T2) · prompt+schema per-rep tags (T3) · persistence/dominant/backward-compat (T4) · API exposure (T5) · component promotion (T6) · FE type/Zod (T7) · cluster-detail viz + confidence badge + 8-axis (T8). Local-Gemma degradation is covered implicitly: the local path returns no `article_needs`, so `aggregate_user_needs` yields `(None, None, 0)` and only the single-label fallback persists — matches the spec.
- **Placeholder scan:** the only non-literal step is T5/Step 1 (reuse the file's existing detail-seed helper) — flagged explicitly because the helper's exact name must be read at execution; the two added lines are shown.
- **Type consistency:** `aggregate_user_needs` signature is identical in T2 (def) and T4 (call); `_upsert_insight` new kwargs match T4 def↔call; `UserNeedDatum` / `distributionToNeeds` / `radarPoints` names match across T6–T8; Zod field names match the backend model names in T1/T5/T7.
