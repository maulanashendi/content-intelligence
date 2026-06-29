# Design: Tempo-relevance filter for `/morning`

**Date:** 2026-06-29
**Status:** Approved (design), pending implementation plan
**Surfaces affected:** `/api/v1/clusters/morning`, `labeling` pipeline step, `ClusterInsight` model, `core` config/taxonomy

## Problem

`/clusters/morning` surfaces the top-10 uncovered leaf clusters of the latest scored
run, "opportunity"-first and ranked by demand (`clusters.py:297`). Its only editorial
gate is `tempo_covered = false`. There is **no notion of editorial fit**: a high-demand
cluster about celebrity gossip, light sports, or viral lifestyle content ranks the same
as one about politics or corruption. Editors report that morning briefing items are
frequently "not Tempo themes."

We want a hard filter so morning only surfaces clusters that match Tempo's editorial
character, defined along two axes classified by an LLM: **desk/category** and
**user-need type** (reusing the existing 8-category user-need taxonomy from `analyst`).

## Decisions (locked)

| Decision | Choice |
|---|---|
| How to define "Tempo theme" | Desk/category **and** user-need, classified via LLM |
| Filter strength | **Hard filter** — off-theme clusters removed from `/morning` entirely |
| Gating logic | Cluster passes only if `desk ∈ allow-list` **AND** `user_need ∉ deny-list` |
| Scope | **`/morning` only**. Classification is still computed & stored for all clusters. |
| Classification approach | **Fold into the existing labeling LLM call** (Approach A) |
| `/deferred` cleanup | **Out of scope** — separate workstream, requires explicit confirmation (see below) |

## Why Approach A (fold into labeling)

The daily scheduled pipeline already runs `labeling` per leaf cluster: it calls an LLM
(`generate_cluster_insight`) with representative articles and upserts results into
`ClusterInsight` (`labeling/pipeline.py:215`). Adding `desk_category` and
`user_need_category` to that same structured-output call costs ~zero extra LLM spend
(same round-trip, more output fields), fits the existing pattern, and respects the
module boundary rule (no cross-batch-module imports). Rejected alternatives:

- **B (separate classification step):** doubles LLM calls per cluster in the 06:00 run.
- **C (reuse `analyst` 16-feature engine at cluster level):** most expensive (one LLM
  call per representative article × cluster) and violates "batch modules never import
  each other" (`labeling → analyst`). The user explicitly asked to "tembak lewat LLM",
  i.e. a direct classification, not the rule engine.

Tradeoff accepted: Approach A reuses the **taxonomy** (the 8 user-need names + their
definitions, plus a fixed desk list) as prompt context, but lets the LLM pick directly
rather than running the deterministic `rank_user_needs` rule engine. If auditable,
deterministic user-need scoring is later required, that is the argument for revisiting C.

## Design

### 1. Data model — `ClusterInsight` (+ Alembic migration)

Add two **nullable** columns to `core.models.ClusterInsight`:

- `desk_category: str | None`
- `user_need_category: str | None`

Both nullable: clusters left unlabeled (beyond `labeling_max_clusters`, or on LLM
failure) have no classification. Under the hard filter, NULL is excluded from `/morning`
naturally — consistent and safe.

**No `tempo_relevant` boolean is stored.** We persist the raw categories and apply the
allow/deny policy at read-time in the `/morning` `WHERE`. Rationale: the allow/deny lists
are policy editors may want to tune via env without re-running the pipeline. Baking a
boolean at write-time would force a full re-label on every policy change. This mirrors the
codebase's existing philosophy (store raw signals; threshold/classify at read or in
scoring).

Migration: Alembic autogenerate, run from `backend/`.

### 2. Shared taxonomy — `core`

Define canonical constants in `core` (single source of truth, because `labeling` cannot
import `analyst`):

- `DESK_CATEGORIES` — the fixed enum the LLM may choose from:
  `Politik, Hukum, Nasional, Ekonomi & Bisnis, Internasional, Investigasi,
  Sains & Teknologi, Lingkungan, Hiburan, Olahraga, Lifestyle, Selebriti, Otomotif,
  Lainnya`.
- `USER_NEED_CATEGORIES` — the 8 existing user needs:
  `Update me, Keep me engaged, Educate me, Give me perspective, Inspire me, Divert me,
  Help me, Connect me`.

Add to `core.config.Settings` (env-overridable) the **policy** lists:

- `morning_allowed_desks: list[str]`
  default = `[Politik, Hukum, Nasional, Ekonomi & Bisnis, Internasional, Investigasi,
  Sains & Teknologi, Lingkungan]`
- `morning_denied_user_needs: list[str]`
  default = `[Divert me, Keep me engaged]`

De-duplicating `analyst`'s existing taxonomy (it hardcodes user-need names in
`category.py` and desk examples in `schemas.py`) to import from `core` is an **optional
follow-up**, not part of this spec, to avoid unrelated refactoring.

### 3. Labeling LLM call — extend structured output

- Extend the structured-output schema behind `generate_cluster_insight`
  (`labeling/schemas.py`, prompt in `labeling/prompts.py`) with `desk_category` and
  `user_need_category` (constrained to the enums above).
- Prompt: add the valid desk list and the 8 user-need definitions (reused from the
  `analyst` taxonomy text), instructing the LLM to pick exactly one of each based on the
  representative articles.
- `_upsert_insight` (`labeling/pipeline.py:188`) extended to write the two new fields,
  preserving its non-destructive contract (only overwrite when the new value is non-None).
- Validation: a value outside the enum is coerced to `None` → the cluster is excluded
  from `/morning`. Safe default under hard filter.

### 4. `/morning` query change

Add to the `WHERE` in `morning_clusters` (`clusters.py:297`):

```python
ClusterInsight.desk_category.in_(settings.morning_allowed_desks),
ClusterInsight.user_need_category.notin_(settings.morning_denied_user_needs),
```

- `IN (allow)` excludes NULL `desk_category` naturally.
- `NOT IN (deny)` excludes NULL `user_need_category` (SQL three-valued logic) — which is
  exactly the desired behavior under a hard filter (unclassified = excluded).
- `_ranking_order()` is unchanged (opportunity-first, demand). No ranking change.

### 5. API contract — expose new fields

Add `desk_category: str | None` and `user_need_category: str | None` to `ClusterSummary`
and populate them in `_to_summary` (`clusters.py:128`). Additive and backward-compatible.
OpenAPI (`/openapi.json`) updates automatically from the Pydantic model. This lets the
frontend render a desk / user-need badge. The fields appear on every endpoint that
returns `ClusterSummary` (detail, bento via summary, etc.), but **only `/morning` filters
on them**.

### 6. Pipeline ordering & interaction

Daily run order: cluster → **label** (writes `desk_category`, `user_need_category`) →
**score** (writes signals/quadrant). Both upsert `ClusterInsight`:

- Scoring's `pg_insert ... on_conflict_do_update` (`scoring/pipeline.py:92`) sets only its
  own column set; it does not touch the two new columns, so they are preserved.
- Labeling's `_upsert_insight` is non-destructive per-field.

No write conflict.

**Known consequence:** clusters beyond `labeling_max_clusters` are never classified →
never appear in `/morning`. Acceptable: the cap prioritizes by trend match + member count,
and `/morning` is top-10, so top clusters are always labeled.

### 7. Deployment / backfill (required step)

After the migration, existing `ClusterInsight` rows have `desk_category = NULL`. Under the
hard filter, **`/morning` returns empty until the next labeling run (06:00 WIB)**.

Required post-deploy step — re-label current clusters in place (no new run):

```bash
docker compose --profile manual run --rm pipeline label
```

This must be in the deploy checklist. (It re-labels `is_current` leaf clusters of the
served run, populating the two new columns on the current scored run's insights.)

### 8. Testing

- **Unit (labeling):** structured output parses `desk_category` / `user_need_category`;
  out-of-enum value → `None`.
- **Unit (API):** `/morning` `WHERE` excludes off-desk and denied-user-need clusters,
  includes allowed ones. Extend `api/tests/test_clusters.py` fixtures with the new columns.
- **E2E (`pipeline/tests/test_e2e.py` patterns):** a cluster classified `Hiburan` /
  `Divert me` does not appear in `/morning`; a `Politik` / `Update me` one does.
- **Migration:** `alembic upgrade head` succeeds; columns nullable.

### 9. Out of scope

- **`/deferred` cleanup.** Investigation (2026-06-29) shows `/clusters/deferred` is not
  consumed by any live frontend feature (only generated types + MSW mocks reference it),
  but it **is** a documented live endpoint (CLAUDE.md, OpenAPI) with backend tests
  (`test_clusters.py`, `test_clusters_no_gsc_leak.py`, `pipeline/tests/test_e2e.py`).
  Removing it is an **API contract change**, not dead-code deletion. The config
  `scoring_deferred_velocity_min` is a genuine orphan (set only in a test, never read).
  Treat as a separate task requiring explicit confirmation before removal.
- De-dup of `analyst` taxonomy into `core` (optional follow-up).
- Filtering `/bento`, `/quadrant`, `/current`.
- Backfilling historical runs (current run handled by §7; older runs filtered out until
  naturally re-labeled, which does not matter since only the latest scored run is served).

## Open questions

None blocking. Allow/deny default lists are starting values; editors can tune via env
(`morning_allowed_desks`, `morning_denied_user_needs`) without code changes.
