# PR4 — API contract + D35 governance + opportunity ranking

**Branch:** `feat/pr4-api-demand-performance`
**Title:** `feat(api): expose editorial quadrant, hide raw GSC (D35)`
**Depends on:** PR3 (insight columns exist).

## Goal

Surface the demand×performance signals through the API, rank `/morning` by the
opportunity quadrant, and resolve the GSC-exposure governance tension.

## Governance — write D35 first

Current state contradicts itself:
- `constraints.md:73` — GSC metrics "must never be returned in API responses."
- `constraints.md:14,20` — internal performance metrics for display are deferred.
- Yet `clusters.py` already returns `tempo_gsc_impressions` (raw GSC) — drift.

**D35 (`docs/decisions.md`):** re-scope the rule.
- *Raw GSC numbers* (clicks, impressions, position, CTR) remain hidden — the
  separate Tempo internal dashboard owns those.
- *Derived editorial levels* (`demand_score`, `high_demand`, `performance_level`,
  `editorial_quadrant`) are signals, not metrics, and may be returned — same
  category as the existing `underperformed` / `tempo_covered` booleans.
- Records the PR1 window/keyword fix and the 2×2 model.

Update `docs/constraints.md:14/20/73` to reference D35 and the levels/metrics
distinction.

## Changes

### 1. `backend/packages/api/src/api/routes/clusters.py`

`ClusterSummary`:
- **Add:** `demand_score: float | None`, `high_demand: bool | None`,
  `performance_level: str | None`, `editorial_quadrant: str | None`.
- **Remove:** `tempo_gsc_impressions` (raw GSC — fixes drift). Drop
  `gsc_demand_gap` (superseded by `editorial_quadrant == "opportunity"`).
- `_to_summary` updated to map the new fields; keep `tempo_covered`,
  `last_internal_days_ago`, `underperformed`.

`/morning` ordering — opportunity first:

```python
.order_by(
    # opportunity quadrant on top
    (ClusterInsight.editorial_quadrant == "opportunity").desc(),
    ClusterInsight.demand_score.desc().nullslast(),
    ClusterInsight.trend_match_count.desc(),
    ArticleCluster.member_count.desc().nullslast(),
)
```

`/deferred` — re-express in terms of the new fields where it referenced
velocity/coverage; behaviour preserved.

Update each changed route's `response_model` + one-line summary in the same
commit (per the API-contract rule).

### 2. Tests

- `backend/packages/api/tests/test_clusters_no_gsc_leak.py` — assert no raw GSC
  field (`gsc_impressions`, `tempo_gsc_impressions`, `ctr`, `avg_position`) is in
  the response; assert derived levels **are** present.
- `backend/packages/api/tests/test_clusters.py` — `/morning` returns opportunity
  clusters first; update fixtures for new columns.
- `test_clusters_returns_label.py` — adjust fixture fields.

### 3. Frontend API package codegen

- `cd frontend && npx openapi-typescript@7` → regenerate
  `frontend/packages/api/src/schemas.ts`.
- Update `frontend/packages/api/src/queries.ts` / `index.ts` types if the
  morning/detail response types are referenced explicitly.

## Acceptance criteria

- `pytest packages/api` green.
- `/openapi.json` shows the new fields and **no** raw GSC field.
- `GET /api/v1/clusters/morning` returns opportunity clusters first; no raw GSC
  leaks.
- FE typecheck passes against regenerated schema.

## Rollback

Revert route + schema changes and re-run FE codegen. D35 stays as a historical
record (mark superseded if fully reverted).
