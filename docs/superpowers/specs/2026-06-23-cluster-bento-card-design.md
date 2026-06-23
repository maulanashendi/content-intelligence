# Cluster Bento Card on `/morning` — Design

**Date:** 2026-06-23
**Status:** Approved design, pre-implementation
**Surface:** Frontend `/morning` + two new read-only API endpoints + a scoped reversal of constraint D35.

## 1. Problem & goal

`/morning` currently surfaces clusters as a dense table (`ArticleClustersCard` → `ClusterTable`). We want a **card-based "bento" view**: a 4×2 grid of compact cluster cards an editor can scan at a glance, drilling into any one for the numbers behind it.

The card must surface (per the request): label, status, velocity, kompetitor, trend, jumlah artikel, total internal views, jumlah artikel kita, last-competitor timestamp, last-internal timestamp, and a small line chart of competitor article volume per hour.

Two requested items were resolved during brainstorming:
- **"Jumlah cluster turunan" is dropped.** Clustering is single-level; `/morning` returns only leaf clusters (`_leaf_guard`), so a child-cluster count is structurally always 0.
- **"Total views" requires a scoped reversal of D35** (see §6). Decided: expose **GSC clicks** as `views`.

## 2. Interaction model (the key decision)

The card has three tiers, revealed progressively to keep the grid scannable:

- **Tier 1 — resting state (always visible):** quadrant **status** chip, the topic **label** (serif), and **velocity**. ~3 data points per card; the 4×2 grid stays calm.
- **Tier 2 + Tier 3 — on click (expand):** the card expands to span 2 grid columns into a "dossier" revealing:
  - **Tier 2 — `Permintaan`:** kompetitor, trend, artikel · **`Liputan kita`:** artikel kita, views
  - **Tier 3:** the **48-hour competitor volume line chart** + last-competitor / last-internal timestamps.

Behavior: single-open accordion (opening one collapses others); click again to collapse; keyboard accessible (`role="button"`, `aria-expanded`, Enter/Space); `prefers-reduced-motion` respected.

**Pagination:** the grid shows 8 cards; a **"Tampilkan 8 lagi"** button reveals 8 more each click, until all current clusters are shown (driven by a `total` count from the API), then the button disables.

**Architectural consequence:** because Tier 3 only appears on click, the **chart series is loaded lazily per card on expand** — it never ships with the list. This keeps the list endpoint light and the time-series truly on-demand.

## 3. Design-system adaptation (mockup → our system)

The approved HTML mockup used a standalone palette. Implementation adapts every element to the existing design system (`tokens.ts` / `globals.css`):

| Mockup element | Implemented with |
| --- | --- |
| Quadrant chip colors (amber/green/blue/gray) | Existing `QUADRANTS` map from `opportunity-matrix-card.tsx` (`--warn-soft`/`--warn` opportunity, `--ok-soft`/`--ok` winning, `--info-soft`/`--info` evergreen, `--bg-sunken`/`--line-strong` ignore) + Indonesian labels (Peluang/Menang/Evergreen/Abaikan). Refactor that map to an exported `quadrants.ts` shared within the `morning` feature. |
| Cool-gray ground & white cards | `--bg`, `--bg-elev`, `--line`, `--line-strong`, `--radius-lg` |
| Serif topic headline | `--font-serif` (`.serif` utility) — already `"Source Serif 4", Georgia, serif` |
| Body / data text + numbers | `--font-sans` (Geist), `--fg`/`--fg-muted`/`--fg-faint`, `tabular-nums` |
| Velocity (number + arrow) | Reuse the `VelocityBar` primitive (number + bar) for consistency with the table; directional arrow is an optional enhancement, not required. |
| Sparkline accent | `--accent` for the line; faint `--accent-soft`/low-alpha fill for the area |
| Card section wrapper | Match `NewsVolumeTrendCard`: `background: var(--bg-elev); border: 1px solid var(--line); border-radius: var(--radius-lg)` |
| "Show more" button | `@ei-fe/ui` `Button` primitive |

No new legacy global classes (`.card`/`.kw-row`); Tailwind + tokens + `@ei-fe/ui` primitives only.

## 4. Backend

No database migration is needed: `views` reuses the existing `cluster_insight.gsc_clicks` column; internal count and last-article timestamps are computed on-read; child-cluster count is dropped.

### 4.1 Bento list endpoint

`GET /api/v1/clusters/bento?limit=8&offset=0`

- **Result set:** all **current leaf clusters** (reuse `_resolve_cluster_filter()` + `_leaf_guard()`), inner-joined to `ClusterInsight` — across **all quadrants** (does *not* apply morning's `tempo_covered.is_(False)` filter).
- **Ranking:** identical ORDER BY to `/morning`, extracted into a shared `_ranking_order()` helper so the two cannot drift: opportunity-first → `demand_score` desc nullslast → `trend_match_count` desc → `member_count` desc nullslast → **`ArticleCluster.id`** (added tiebreaker for stable pagination).
- **Params:** `limit: int = Query(8, ge=1, le=50)`, `offset: int = Query(0, ge=0)`.
- **On-read enrichment** (one grouped query over the page's cluster IDs):
  ```sql
  SELECT acm.cluster_id,
         COUNT(*) FILTER (WHERE cs.source_type = 'internal')                      AS internal_article_count,
         MAX(COALESCE(a.published_at, a.created_at)) FILTER (WHERE cs.source_type = 'rss')      AS last_competitor_at,
         MAX(COALESCE(a.published_at, a.created_at)) FILTER (WHERE cs.source_type = 'internal') AS last_internal_at
  FROM article_cluster_member acm
  JOIN article a        ON a.id = acm.article_id
  JOIN content_source cs ON cs.id = a.source_id
  WHERE acm.cluster_id IN (:page_ids)
  GROUP BY acm.cluster_id
  ```
- **`total`:** count of the full ranked set (same WHERE, no limit/offset) so the frontend knows when to stop "Show more".

**Response models (Pydantic):**
```python
class BentoCard(BaseModel):
    id: uuid.UUID
    label: str | None
    editorial_quadrant: str | None
    trend_velocity: float | None
    competitor_count: int | None
    trend_match_count: int | None
    member_count: int | None
    views: int                       # = ClusterInsight.gsc_clicks (see §6)
    internal_article_count: int
    last_competitor_at: UtcDateTime | None
    last_internal_at: UtcDateTime | None

class BentoListResponse(BaseModel):
    cards: list[BentoCard]
    total: int
    served_at: UtcDateTime | None
    is_stale: bool
    max_age_hours: int
```
Summary: `"Cluster bento — all current clusters ranked, paginated, for the card grid"`.

### 4.2 Per-cluster competitor-volume endpoint (lazy chart)

`GET /api/v1/clusters/{id}/volume-trend?bucket=hour`

- Mirrors `articles.py::volume_trend` (WIB `date_trunc` bucketing, `_dense_bucket_starts`, 48 hourly / 30 daily buckets) but **scoped to one cluster's members** via `article_cluster_member`, split by `source_type`.
- Reuses the existing `VolumeTrendResponse` / `VolumeBucket` schema (`competitor_count` + `internal_count` per bucket). The card plots the competitor line; internal stays available for future use.
- `404` if the cluster id does not exist.
- Summary: `"Competitor vs internal article volume per WIB bucket, scoped to one cluster"`.

## 5. Frontend

### 5.1 Data layer (`packages/api`)
- `schemas.ts`: add `BentoCardSchema`, `BentoListResponseSchema`. Reuse `VolumeTrendResponseSchema` for the per-cluster chart.
- `keys.ts`: add `clusterKeys.bento(limit: number)` and `clusterKeys.volumeTrend(id: string, bucket)`.
- `queries.ts`:
  - `useClusterBento(limit: number)` → `apiGet("/clusters/bento?limit=${limit}&offset=0", BentoListResponseSchema)` with `placeholderData: keepPreviousData` (growing-limit pagination; offset reserved on the backend for future use).
  - `useClusterVolumeTrend(id: string, enabled: boolean)` → `apiGet("/clusters/${id}/volume-trend?bucket=hour", VolumeTrendResponseSchema)`, `enabled` (fires only when a card is expanded), `staleTime: 5*60*1000`.

### 5.2 Components (`packages/features/src/morning`)
- `quadrants.ts` — extract & export the quadrant map from `opportunity-matrix-card.tsx`; both cards import it.
- `sparkline.ts` — single-series line builder modeled on `volume-chart.ts` (d3 `scaleLinear`), returning `{ linePath, areaPath, lastPoint, innerWidth, innerHeight }`.
- `cluster-bento-card.tsx`:
  - `ClusterBentoCard` (section) — fetches `useClusterBento(shown)`, owns `shown` state + "Show more", renders the responsive grid (`repeat(4,1fr)` → `2` → `1`), handles `LoadingState`/`ErrorState`/`EmptyState`.
  - `BentoCard` (one cell) — Tier 1 always rendered; owns `open` state, `aria-expanded`, keyboard handler; on open, mounts Tier 2 + Tier 3 and triggers `useClusterVolumeTrend(id, open)`; chart drawn with `useElementWidth` + `sparkline.ts`. The quadrant chip falls back gracefully when `editorial_quadrant` is null.
  - **Click semantics (disambiguated):** clicking/Enter on the card body toggles expand/collapse. Navigation to `/clusters/{id}` is a dedicated **"Buka klaster →"** link inside the expanded Tier 3 (so card-toggle and navigation never collide).
- `morning-view.tsx`: insert `<div style={{ padding: "20px 28px 0" }}><ClusterBentoCard /></div>` after `<NewsVolumeTrendCard />`, before `<ClusterForceGraph />`.

## 6. Constraint D35 reversal (scoped)

Decision: expose **GSC clicks** as an aggregated per-cluster `views` figure. The reversal is **narrow** — impressions, CTR, and average position remain internal-only.

- **`docs/constraints.md` (D35)** and the **`CLAUDE.md` hard rule**: amend to "GSC **clicks** may be returned as an aggregated per-cluster `views` value; GSC **impressions, CTR, and average position** are scoring inputs only and never returned via API."
- **`docs/decisions.md`:** add an entry recording the partial reversal, its rationale (editorial value of click-through on the bento card), and its narrow scope.
- **`backend/.../tests/test_clusters_no_gsc_leak.py`:** keep `gsc_impressions`/`gsc_ctr`/`gsc_avg_position` (and the literal field name `gsc_clicks`) in `_RAW_GSC_FIELDS`; **extend coverage to `/api/v1/clusters/bento` and `/api/v1/clusters/{id}/volume-trend`**; add a positive assertion that `views` is present on the bento response. (The exposed field is named `views`, never `gsc_clicks`, so the literal-string guard still holds.)
- **`CLAUDE.md` + OpenAPI:** add `/api/v1/clusters/bento` and `/api/v1/clusters/{id}/volume-trend` to the live read-endpoint list; endpoint changes ship Pydantic models + `response_model=` + summaries in the same commit (API-contract rule).

## 7. Testing

**Backend (TDD):**
- Bento: ranking parity with `/morning`'s ORDER BY; includes all quadrants (not only uncovered); stable pagination via `limit`/`offset` with the id tiebreaker; correct `views`, `internal_article_count`, `last_competitor_at`, `last_internal_at`; correct `total`.
- Per-cluster volume-trend: correct WIB bucketing; competitor/internal split; only the cluster's members counted; `404` on unknown id.
- GSC leak: extended as in §6.

**Frontend:** typecheck; render sanity (resting shows Tier 1 only; expand reveals Tier 2/3 and triggers the lazy chart fetch; "Show more" increments and disables at `total`); manual verification on `/morning`.

## 8. Out of scope
- No migration / no new DB columns.
- No change to `/morning`, `ClusterSummary`, the table, KPIs, matrix, or force graph.
- "Modal" expansion (inline accordion chosen); directional velocity arrow (VelocityBar reused); child-cluster count (dropped).
