# PR3 — Split scoring into demand + performance + 2×2 quadrant

**Branch:** `feat/pr3-demand-performance-scoring`
**Title:** `feat(scoring): demand + performance modules, editorial quadrant (D35)`
**Depends on:** PR1 (window/metric), PR2 (`article_gsc_metric` populated).

## Goal

Turn the raw signals into the two editorial axes the app is about:
**external demand** (high/low) and **internal performance**
(high/low/none/too_early), combined into an `editorial_quadrant`.

## Conceptual model

```
                 internal performance (GSC, 7d)
                 low / none              high
 demand  high │  opportunity 🔥        winning ✅
        low   │  ignore 💤             evergreen 🪦
```
`too_early` = covered but the internal article is too new to have GSC data.

## Changes

### 1. Schema (`backend/packages/core/src/core/models.py` → Alembic autogenerate)

Add to `ClusterInsight`:

| Column | Type | Exposed via API? |
| ------ | ---- | ---------------- |
| `demand_score` | `Float` null | yes |
| `high_demand` | `Boolean` null | yes |
| `performance_level` | `String` null (`high`/`low`/`none`/`too_early`) | yes |
| `editorial_quadrant` | `String` null (`opportunity`/`winning`/`evergreen`/`ignore`/`too_early`) | yes |
| `gsc_impressions` | `Integer` null | **no** (internal) |
| `gsc_clicks` | `Integer` null | **no** |
| `gsc_ctr` | `Float` null | **no** |
| `gsc_avg_position` | `Float` null | **no** |

String (not a PG enum) for the two level columns — matches D27's lean away from
enums and keeps the migration trivial; allowed values documented + validated in
code. Keep `tempo_covered`. `gsc_demand_gap` / `tempo_gsc_impressions` are
superseded — drop them in the same migration (PR4 removes the API fields).

Update `docs/schema.dbml` to mirror.

### 2. Scoring modules (`backend/packages/scoring/src/scoring/`)

Split `pipeline.py` into:

- **`demand.py`** — per cluster, over `analysis_window_days`:
  `trend_keyword_count`, `trend_interest` (PR1 queries), `competitor_count`,
  `competitor_freshness_days`, `velocity`. Combine into a normalized
  `demand_score ∈ [0,1]`. Classify `high_demand` by **percentile within the
  run** — top tercile by default; `settings.demand_high_percentile = 0.66`.
- **`performance.py`** — per cluster, aggregate `article_gsc_metric` (internal
  members only) over the GSC window → `gsc_impressions/clicks/ctr/avg_position`.
  Derive `performance_level`:
  - `none` — `tempo_covered = false` (no internal article).
  - `too_early` — covered but no GSC rows in window (article too new).
  - `high` / `low` — covered with GSC data: `high` when impressions are in the
    top percentile **and** position/CTR are healthy; `low` otherwise (includes
    the existing `underperformed` thresholds). Percentile config
    `performance_high_percentile = 0.66`.
- **`pipeline.py`** — orchestrator: run `demand` + `performance`, then derive
  `editorial_quadrant` and upsert the full `cluster_insight` row.

> Percentiles are computed over the current run's clusters in Python after the
> facts are loaded (the existing code already builds a `facts_by_cluster` dict —
> compute cut points from that, no extra query).

### 3. Orchestration (`backend/packages/pipeline/src/pipeline/cluster_label_score.py`)

Call demand → performance → combine (replacing the single `scoring.pipeline.run`
call). Keep it inside the one daily cycle (no second scheduler — agreed simple
path).

### 4. Config (`core/config.py`)

`demand_high_percentile: float = 0.66`, `performance_high_percentile: float = 0.66`.
Keep existing `gsc_underperform_*` thresholds for the `low` floor.

## Tests

- Split `test_scoring.py` → `test_demand.py` + `test_performance.py`.
- `test_demand.py`: percentile boundary (cluster just above/below cut →
  high/low); demand_score monotonic in inputs.
- `test_performance.py`: `none` when uncovered; `too_early` when covered but no
  GSC; `high`/`low` by percentile + underperform floor; impression-weighted
  position aggregation.
- New `test_quadrant.py` (or in pipeline tests): the 2×2 mapping incl.
  `too_early`.
- Update `backend/packages/pipeline/tests/test_cluster_label_score_integration.py`
  and `test_e2e.py` for the new insight columns.

## Acceptance criteria

- `pytest packages/scoring packages/pipeline` green.
- Local `run-daily` → `cluster_insight` has `high_demand`, `performance_level`,
  `editorial_quadrant` populated; some `opportunity` clusters exist; GSC
  aggregates populated for covered clusters.

## Rollback

Revert migration (drop new columns, restore `gsc_demand_gap`/
`tempo_gsc_impressions`) + scoring modules. PR4/PR5 must be reverted first.
