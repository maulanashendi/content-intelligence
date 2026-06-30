# Design: User-Need Distribution as a Cluster Insight

**Date:** 2026-06-30
**Branch:** `worktree-feat+cluster-user-need-distribution` (worktree off `master` @ `5f6a1e0`)
**Surfaces:** `labeling` pipeline, `core` schema/migration, `api` `/clusters/*`, frontend `clusters` feature + `@ei-fe/ui`.

## Context

Today "user need" lives at two disconnected depths (see CLAUDE.md):

- **Cluster level (shallow):** the labeling step asks the LLM for **one** holistic
  `user_need_category` per cluster (`KEBUTUHAN` field). Stored on
  `cluster_insight.user_need_category`. Used only as an on/off gate by `/clusters/morning`
  (`morning_denied_user_needs`).
- **Article level (deep, but stateless):** the `analyst` package scores an article against
  all 8 needs via a 16-feature rule engine (`analyst/category.py`). Rendered as radar/bars,
  but never persisted and never fed back into the cluster pipeline.

This work makes user-need a **first-class cluster insight**: a per-cluster **distribution
profile** over the 8 News-Needs categories, grounded in counting the cluster's
representative articles — not a single holistic guess.

### Decisions locked during brainstorming

1. **Role:** a rich **distribution profile** for display. It does NOT change scoring/ranking.
2. **Signal source:** the **existing single insight LLM call** (1 call/cluster, **no added
   cost**) is extended to tag each representative article; the distribution is computed by
   **counting** those tags.
3. **Granularity:** **up to 2 needs per article** (an article can serve two needs). The
   distribution is a frequency count (totals may exceed the article count).
4. **Scope:** **backend + frontend**.

## Goal & non-goals

**Goal:** persist a grounded per-cluster user-need distribution in `cluster_insight`, expose
it via the cluster API, and visualize it (radar + bars) on the cluster detail view.

**Non-goals (YAGNI):**

- ❌ No change to scoring / ranking / `editorial_quadrant`.
- ❌ No change to the `analyst` article-level endpoints (Jalur B stays stateless).
- ❌ The local Gemma path is NOT brought to full parity for the distribution (see §Computation).
- ❌ No change to the `/morning` filter semantics (it keeps gating on the single dominant need).

## Data model & schema (`core`)

`cluster_insight` gains **two** columns; the existing `user_need_category` is retained and
re-purposed as the **dominant** need.

| Column | Type | Contents |
| --- | --- | --- |
| `user_need_distribution` | `JSONB`, nullable | `{"Update me": 3, "Give me perspective": 2, ...}` — **all 8 canonical keys** (zeros included) so the radar always has 8 axes. `NULL` when no grounded tags exist. |
| `user_need_reps_tagged` | `Integer`, nullable | Number of representative articles that contributed ≥1 valid tag. Sample size → confidence. |
| `user_need_category` (existing) | `String`, nullable | **Dominant** need = argmax of the distribution. Drives the unchanged `/morning` filter. |

SQLAlchemy (`core/models.py`, `ClusterInsight`):

```python
user_need_distribution: Mapped[dict[str, int] | None] = mapped_column(JSONB)
user_need_reps_tagged: Mapped[int | None] = mapped_column(Integer)
```

> **Approach considered & rejected:** a normalized `cluster_user_need(cluster_id, need, count)`
> table. Rejected — the data is read-only, always fetched whole per cluster, never queried
> per-need. JSONB is simpler and consistent with the existing `ARRAY` columns on this table.

Mirror the change in `docs/schema.dbml`. Migration via Alembic autogenerate, run from `backend/`.

## Computation flow (`labeling`)

The single existing insight call now also returns per-representative need tags; the pipeline
aggregates them deterministically.

- **Prompt** (`labeling/prompts.py`, `_CLUSTER_INSIGHT_USER_API`): for each `[Sudut i]`, emit
  **up to 2** needs chosen from `USER_NEED_CATEGORIES`.
- **Schema** (`labeling/schemas.py`, `ClusterInsightLLM`): add
  `article_needs: list[list[str]] | None = None` — one inner list (≤2 needs) per representative,
  in the same order the reps were presented.
- **Aggregation** — new pure function (`labeling/pipeline.py`), unit-testable in isolation:

  ```python
  def aggregate_user_needs(
      article_needs: list[list[str]] | None,
  ) -> tuple[dict[str, int] | None, str | None, int]:
      """Returns (distribution over all 8 needs, dominant need, reps_tagged)."""
  ```

  - Each raw need is validated via `core.taxonomy.normalize_user_need`; unknown/hallucinated
    values are dropped.
  - `distribution` is initialized to `{need: 0 for need in USER_NEED_CATEGORIES}` and
    incremented per valid occurrence.
  - `reps_tagged` counts inner lists that contributed ≥1 valid need.
  - `dominant` = need with the highest count; **tie-break by `USER_NEED_CATEGORIES` order**
    (deterministic, test-stable).
  - If no valid tags: returns `(None, None, 0)`.

- **Persistence** (`_upsert_insight`): extend the signature with
  `user_need_distribution` and `user_need_reps_tagged`; remain **non-destructive** (only
  overwrite a field when the new value is non-`None`). `user_need_category` is set from
  `dominant` (falling back to the LLM's holistic `user_need_category` when `article_needs`
  is empty, so existing behavior is preserved).
- **Local Gemma path** (`_cluster_insight_local`): per-article multi-tag parsing from a 2B
  model is unreliable, and production is **full-API** (per project memory). The local path
  keeps emitting the single `KEBUTUHAN` → `user_need_category` as today, with
  `user_need_distribution = None`, `user_need_reps_tagged = None`. Documented explicitly.

## API (`api`)

- `ClusterSummary` (`api/routes/clusters.py`): add
  `user_need_distribution: dict[str, int] | None` and `user_need_reps_tagged: int | None`.
  `ClusterDetail` inherits both. `BentoCard` is untouched.
- Update `_to_summary(...)` to map the two new fields from the insight.
- Per the API-contract rule (CLAUDE.md): update the affected route `summary` lines and let
  `/openapi.json` regenerate in the same commit. No new endpoints, no status-code changes.
- **`/morning` filter is unchanged** — still gates on `ClusterInsight.user_need_category`
  (dominant). Side benefit: dominant is now grounded in counting, so the gate is more robust
  for free.

## Frontend (`clusters` feature + `@ei-fe/ui`)

- **Promote** the presentation-only components from `features/analyst` to `@ei-fe/ui`
  (layering rule: a component used by ≥2 features promotes): `UserNeedsRadar`, `UserNeedsBars`,
  and the `radarPoints` geometry helper. Their prop contract (`needs: {key,label,value}[]`)
  is unchanged. Re-point the `analyst` feature to import them from `@ei-fe/ui` (single source).
- **Per-feature adapters stay per-feature** (this resolves the 6-vs-8 axis question cleanly):
  - `analyst` keeps `orderedUserNeeds` + its existing 6-axis `USER_NEED_ORDER`.
  - `clusters` adds an **8-axis** order/label map + a `distributionToNeeds(distribution, repsTagged)`
    adapter mapping counts → `needs[]` with `value = round(count / max(counts) * 100)`
    (empty/`null` distribution → no chart).
- Render radar + bars on the **cluster detail** view, with the sample-size confidence badge (below).
- Regenerate FE types from `/openapi.json` (`npx openapi-typescript@7`, per project memory).

## Robustness ("kokoh") provisions

1. **Explicit sample size** (`user_need_reps_tagged`) → FE shows an "indikatif" badge when the
   sample is small (e.g. `< 3`).
2. **Deterministic:** `temperature=0` (already) + counting + ordered tie-break.
3. **Validation:** only the 8 canonical needs enter the distribution; everything else dropped.
4. **Grounded:** based on counting real representative articles, not one holistic guess.
5. **Backward-compatible & non-destructive:** dominant still drives `/morning`; upsert only
   overwrites non-`None` fields.

## Testing

- `labeling`: `aggregate_user_needs` (counts, dominant, ordered tie-break, drop-unknown,
  empty→`(None,None,0)`); `_upsert_insight` writes the two new fields non-destructively; the
  API insight path returns and persists `article_needs`.
- `api`: cluster summary/detail responses include `user_need_distribution` +
  `user_need_reps_tagged`; `/morning` behavior unchanged.
- `frontend`: bun test for `distributionToNeeds` (counts→needs[], normalization, empty/0
  sample); radar/bars render from the promoted `@ei-fe/ui` components.
- Migration: Alembic autogenerate produces exactly the two columns; `upgrade`/`downgrade` clean.

## Invariants & constraints (the reviewer's lens)

1. **8-key distribution.** When non-`null`, `user_need_distribution` has exactly the 8
   `USER_NEED_CATEGORIES` keys (zeros included). Sum of values == total valid tags.
2. **Dominant consistency.** `user_need_category` (when set from a non-`null` distribution)
   equals the argmax of `user_need_distribution`, tie-broken by `USER_NEED_CATEGORIES` order.
3. **No cost regression.** Still **one** LLM call per cluster in the labeling step.
4. **`api` purity.** No torch/ML imports in `api`. No `print()` — JSON logging only. src layout.
5. **Taxonomy single source.** Need strings come only from `core.taxonomy`
   (`USER_NEED_CATEGORIES` / `normalize_user_need`); the labeling path must not hardcode a
   second copy.
6. **Frontend layering.** Promoted components live in `@ei-fe/ui` (Tailwind + tokens + ui
   primitives only, no legacy `.card`/`.kw-row`). No cross-feature imports; adapters stay
   in their own feature.
7. **API contract.** Pydantic model + `response_model=` + route `summary` updated in the
   same commit as any signature change; `/openapi.json` is the contract.

## Concurrency note (active parallel work)

A live session is implementing `feat/morning-dna-toggle` in the main checkout, also editing
`api/routes/clusters.py` (it refactors the `/morning` desk+user-need clause into a shared
`_dna_filter()` helper and adds a `dna` param to four endpoints) and appending to
`docs/decisions.md`.

This work is isolated on its own worktree/branch off `master`. Overlap is minor and additive:

- `clusters.py`: our edits are the `ClusterSummary` fields + `_to_summary` mapping (response
  model), in different regions than their where-clause/param changes — expect auto-merge or a
  trivial rebase.
- `docs/decisions.md`: both append a new decision — trivial append conflict.
- No overlap on `core/models.py`, migrations, or the labeling package.

**Reconciliation:** prefer landing `feat/morning-dna-toggle` first, then rebase this branch on
the updated `master`. Our "dominant from distribution" change keeps `user_need_category` a
single string, so their `_dna_filter()` continues to work unchanged.
