# Demo: GitHub Pages Static Build

**Date:** 2026-06-17  
**Audience:** Internal stakeholders / management (non-technical)  
**Delivery:** GitHub Pages URL — click, no server required

## Goal

Produce a fully offline demo of the content intelligence dashboard that stakeholders can access via a single URL. The demo runs the real frontend codebase against mocked JSON data so it looks and behaves identically to production.

## Approach

The existing app already has MSW (Mock Service Worker) wired up with handlers for every API route and JSON fixtures for the data. Mock mode currently only activates in dev. This design enables a production build that boots MSW instead of calling the real backend.

## Changes

### 1. Mock activation — `main.tsx` (1 line)

Change the MSW bootstrap condition from:
```ts
if (import.meta.env.DEV && import.meta.env["VITE_ENABLE_MOCK"] !== "false")
```
to:
```ts
if (import.meta.env.DEV || import.meta.env.VITE_MOCK === 'true')
```

A build with `VITE_MOCK=true` produces a production bundle that intercepts all API calls via MSW. The real backend is never contacted.

### 2. Missing mock handlers — `handlers.ts`

Two endpoints used by the opportunity matrix have no mock handler today:

- `GET /api/v1/clusters/quadrant-summary` → static `QuadrantSummary` object (counts per quadrant)
- `GET /api/v1/clusters/quadrant/:quadrant?limit=N` → filters `morning-clusters` by quadrant assignment, returns `ClusterListResponse`

Quadrant assignment logic (inline in handler, not a separate util):
- `opportunity`: high trend_velocity (≥0.6) + `tempo_covered = false`
- `winning`: high trend_velocity (≥0.6) + `tempo_covered = true`
- `evergreen`: low trend_velocity (<0.6) + `tempo_covered = true`
- `ignore`: low trend_velocity (<0.6) + `tempo_covered = false` + not underperformed
- `too_early`: `tempo_covered = true` + `last_internal_days_ago = null` (GSC not yet available)

### 3. Enriched fixture JSON

All mock data is JSON. No JS logic is added to fixtures.

**`cluster-detail.json`** — currently has 1 cluster (BBM) with `what_happened`, `parties_involved`, `editorial_angle` all `null`. Enrich:
- Fill in `what_happened` (1–2 sentence factual summary)
- Fill in `parties_involved` (array of named actors)
- Fill in `editorial_angle` (concrete editorial recommendation)
- Expand `members` from 6 → 12 articles with real `first_paragraph` text

**`morning-clusters.json`** — add `demand_score` (0.0–1.0) and `performance_score` (0.0–1.0) to each of the 10 clusters so the matrix drill-down shows scores.

**Rich detail for all 10 clusters** — the current `handlers.ts` already handles unknown cluster IDs by generating synthetic members from `morning-clusters`. For the demo, the top 5 clusters (by trend_velocity) get explicit entries in a new `cluster-details-map.json` fixture with filled insight fields. Remaining 5 fall back to the existing synthetic generation.

`cluster-details-map.json` format: `{ "<cluster-id>": { ...ClusterDetail } }` — same shape as `cluster-detail.json`, keyed by cluster ID. The `/clusters/:id` handler checks this map first, then falls back to synthetic generation.

### 4. GitHub Pages deployment

**`vite.config.ts`** — add `base` option:
```ts
base: process.env["VITE_BASE"] ?? "/",
```

**GitHub Actions workflow** — `.github/workflows/demo.yml`:
- Trigger: push to `master` + manual `workflow_dispatch`
- Steps:
  1. `cd frontend && bun install`
  2. `VITE_MOCK=true VITE_BASE=/content-intelligence/ bun run build`
  3. `cp dist/index.html dist/404.html` — fixes React Router deep links on refresh
  4. Deploy `dist/` to `gh-pages` branch via `peaceiris/actions-gh-pages`

The `404.html` copy is the standard GitHub Pages fix for client-side routers: when a user refreshes on `/clusters/abc`, GitHub Pages serves `404.html` (which is `index.html`), React Router hydrates, and the correct view renders.

## Screens covered

All four screens work in the demo:

| Screen | Route | Mock data source |
|--------|-------|-----------------|
| Morning Brief | `/morning` | `morning-clusters.json` + quadrant handlers |
| Cluster Detail | `/clusters/:id` | `cluster-detail.json` / `cluster-details-map.json` / synthetic fallback |
| Articles | `/article` | synthetic via `generateArticles()` (already in handlers) |
| Sources | `/sources` | `mockSources` array (already in handlers) |
| Force Graph | embedded in Morning | uses loaded cluster details |

## Files changed

| File | Change |
|------|--------|
| `frontend/packages/app/src/main.tsx` | 1-line condition change |
| `frontend/packages/app/vite.config.ts` | add `base` option |
| `frontend/packages/app/src/mocks/handlers.ts` | add quadrant-summary + quadrant/:quadrant handlers |
| `frontend/packages/api/tests/mocks/fixtures/cluster-detail.json` | enrich insight fields, expand members |
| `frontend/packages/api/tests/mocks/fixtures/morning-clusters.json` | add demand_score + performance_score |
| `frontend/packages/api/tests/mocks/fixtures/cluster-details-map.json` | new file — top-5 cluster details |
| `.github/workflows/demo.yml` | new file — build + deploy workflow |

## Out of scope

- Deferred clusters screen (`/clustering`) — not a priority view for management demo
- Sources add/delete flows — MSW already handles them, no changes needed
- Any backend changes — demo is frontend-only
