# News Volume Trend chart — design

**Date:** 2026-06-23
**Status:** Approved (design), pending implementation plan

## Goal

Add a bar chart to the Morning Brief showing the volume of news over time, combining
competitor (RSS) and internal (Tempo) articles, so editors can spot **spikes** in news
activity. The x-axis is switchable between **hourly** and **daily** granularity. Bars are
**stacked** (competitor + internal) and the chart is **interactive via hover tooltips**.

## Architecture

A new read-only backend endpoint returns time-bucketed article counts split by source
type. A new self-contained Morning Brief card fetches it and renders a stacked SVG bar
chart (React + `d3-scale`) with a Jam/Hari toggle and hover tooltips.

```
Article + ContentSource (Postgres)
  → GET /api/v1/articles/volume-trend?bucket=hour|day   (new FastAPI route)
  → useVolumeTrend(bucket)  (TanStack Query hook, Zod-validated)
  → NewsVolumeTrendCard      (morning feature, stacked SVG bars + tooltip + toggle)
  → morning-view.tsx         (placed after OpportunityMatrixCard)
```

## Decisions (locked during brainstorming)

1. **Charting:** React + SVG using `d3-scale` for scales. No new dependency (`d3` is
   already in `packages/features`). Tooltip and toggle are hand-built. Respects the
   "no new top-level deps" hard rule.
2. **Bar style:** Stacked — bar height = total volume; segments = competitor (RSS) +
   internal (Tempo). Best for spotting total spikes while keeping source composition.
3. **Default ranges:** `hour` → last 48 hours; `day` → last 30 days.

## Backend — `GET /api/v1/articles/volume-trend`

Lives in `backend/packages/api/src/api/routes/articles.py`.

- **Query param:** `bucket: Literal["hour", "day"] = "day"`.
- **Range (server-controlled, not a query param — YAGNI):** `hour` → 48h back,
  `day` → 30d back. Cutoff computed from "now".
- **Timezone:** WIB is a fixed **UTC+7** (Indonesia has no DST). Bucket boundaries are
  computed in WIB so daily/hourly counts align with the editorial day, not UTC midnight.
  Timestamps are stored as naive UTC (`TIMESTAMP WITHOUT TIME ZONE`); add 7h before
  truncating, subtract 7h to return the UTC instant of each WIB bucket start.
- **Effective timestamp:** `func.coalesce(Article.published_at, Article.created_at)` — the
  established codebase pattern (see `sources.py`).
- **Source split:** join `ContentSource`; `source_type == rss` → competitor,
  `source_type == internal` → Tempo.
- **Zero-fill:** return a **dense** ordered series — every bucket in the range, including
  zeros — so the frontend x-axis is continuous. SQL returns sparse grouped counts; Python
  assembles the dense series by stepping from cutoff to now by the bucket size (trivial
  since WIB offset is constant).

### Response models (Pydantic, defined in-file per convention)

```python
class VolumeBucket(BaseModel):
    bucket_start: UtcDateTime   # UTC instant of the WIB bucket start
    competitor_count: int
    internal_count: int

class VolumeTrendResponse(BaseModel):
    bucket: Literal["hour", "day"]
    buckets: list[VolumeBucket]
    generated_at: UtcDateTime
```

Route declares `response_model=VolumeTrendResponse`, explicit `status_code`, and a one-line
`summary=`. Not GSC data → no constraint conflict.

### Query shape

```sql
-- conceptually:
SELECT date_trunc(:bucket, effective_ts + interval '7 hours') AS wib_bucket,
       source_type,
       count(*) AS cnt
FROM article JOIN content_source ON ...
WHERE effective_ts >= :cutoff
GROUP BY wib_bucket, source_type
```

Python then maps `(wib_bucket, source_type) -> cnt` onto the dense bucket list and converts
each WIB bucket start back to a UTC instant for `bucket_start`.

## Frontend — data layer (`@ei-fe/api`)

- `keys.ts`: extend `articleKeys` with
  `volumeTrend: (bucket: "hour" | "day") => [...articleKeys.all, "volume-trend", bucket]`.
- `schemas.ts`: hand-written Zod `VolumeBucketSchema` + `VolumeTrendResponseSchema`
  (+ inferred TS types).
- `queries.ts`: `useVolumeTrend(bucket)` calling `apiGet("/articles/volume-trend?bucket=...",
  VolumeTrendResponseSchema)`. Default cache (staleTime 5min) matches pipeline cadence.
- `index.ts`: export the hook and types.
- `generated.ts`: regenerate via `bun run gen:api` after the backend endpoint lands.

## Frontend — component (`morning/news-volume-trend-card.tsx`)

- Local state `bucket: "hour" | "day"` (default `"day"`).
- **Segmented Jam/Hari toggle** built with Tailwind utilities + design tokens; switching
  re-runs the query (different key).
- Self-fetches via `useVolumeTrend(bucket)`; renders `LoadingState` / `ErrorState` /
  `EmptyState` from `@ei-fe/ui` for the respective states. `ErrorState.onRetry` invalidates
  the `volumeTrend` key.
- **Stacked SVG chart:**
  - `scaleBand` for x over `bucket_start`; `scaleLinear` for y over the max stacked total.
  - Each bar = competitor segment (muted slate, `--fg-faint`) below internal segment
    (brand `--accent`) — or vice versa, finalized in implementation; Tempo's own coverage
    should read clearly against the competitor baseline.
  - Axis labels formatted in WIB via `Intl.DateTimeFormat` with `timeZone: "Asia/Jakarta"`:
    `14:00` for hour mode, `12 Jun` for day mode. Labels thinned (every Nth) to avoid
    overlap.
  - Small legend: Kompetitor / Internal.
- **Tooltip:** lightweight absolutely-positioned `div` (not the Radix `Tooltip` primitive,
  which is awkward per-bar) that follows the hovered bar; shows WIB time, `Kompetitor n`,
  `Internal n`, `Total n`.
- **Pure helper `buildVolumeChart(buckets, dims)`** returns bar geometry (x, y, heights,
  segment rects, max) — kept side-effect-free so it is unit-testable independent of the DOM.
- Card chrome matches neighboring morning cards (inline style with CSS-var tokens such as
  `var(--bg-elev)`, `var(--line)`); no legacy global CSS classes (`.card`).

## Placement

In `morning-view.tsx`, insert the card full-width **after `OpportunityMatrixCard` and before
`ClusterForceGraph`**, wrapped in the same `padding: "20px 28px 0"` container. Narrative
flow: quadrant context → volume over time → network view.

## Edge cases

- Empty DB / all-zero range → `EmptyState` ("Belum ada data volume berita.").
- A range with some zero buckets still renders a continuous axis (zero-height bars).
- Loading → `LoadingState`; error → `ErrorState` with retry.

## Testing

- **Backend (TDD, pytest)** under `packages/api/tests/`:
  - WIB day bucketing aligns to WIB midnight, not UTC.
  - WIB hour bucketing.
  - rss-vs-internal split is correct.
  - Zero-fill density (count of buckets matches the range).
  - 48h / 30d cutoffs exclude older rows.
  - `coalesce` fallback uses `created_at` when `published_at` is null.
  - Empty DB returns dense all-zero series, not an error.
- **Frontend:** if a unit-test runner (vitest) exists in the workspace, add tests for the
  pure `buildVolumeChart` helper (bar count, heights, stacking order, zero handling) and the
  WIB label formatter. Confirm runner availability during planning; otherwise rely on
  backend tests + manual verification.

## Out of scope

- Configurable arbitrary date ranges / date pickers.
- Per-source (per-feed) breakdown beyond the competitor/internal split.
- Persisting chart state, export, or drill-down navigation.
- Any new charting library.

## Notes

- This work is unrelated to the current `feat/ai-analyst-frontend` branch; implement on a
  fresh branch off `master`.
