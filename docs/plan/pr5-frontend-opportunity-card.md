# PR5 — Frontend "Peluang Editorial" card

**Branch:** `feat/pr5-opportunity-card`
**Title:** `feat(fe): demand × performance opportunity card on morning view`
**Depends on:** PR4 (API exposes the new fields).

## Goal

Show editors the 2×2 at a glance: how many clusters sit in each quadrant, with
the **opportunity** quadrant (high demand, low/no performance) highlighted —
placed directly above the topic cluster map.

## Changes

### 1. New component

`frontend/packages/features/src/morning/opportunity-matrix-card.tsx`

- Props: `clusters` (the morning list; already loaded in `MorningView`).
- Reads the new fields: `editorial_quadrant`, `high_demand`, `performance_level`,
  `demand_score`.
- Renders a 2×2 grid with per-quadrant cluster counts:
  - 🔥 Peluang (opportunity) — emphasized
  - ✅ Menang (winning)
  - 🪦 Evergreen
  - 💤 Abaikan (ignore)
  - plus a small "Baru / pantau" (too_early) chip.
- Clicking the opportunity cell can scroll to / filter the cluster list (optional;
  keep minimal for v1 — counts + highlight).

**Styling rule (constraints.md):** new components must use **Tailwind +
`@ei-fe/ui` primitives only** — no legacy `.card` / `.kpi` / `.kw-row` classes.
Use the existing `@ei-fe/ui` card/primitive; if none fits, compose with Tailwind.

### 2. Placement (`frontend/packages/features/src/morning/morning-view.tsx`)

Insert between `KpiRow` and the `ClusterForceGraph` block (the topic cluster
map, ~line 113):

```tsx
<KpiRow clusters={clusters} />

<div style={{ padding: "20px 28px 0" }}>
  <OpportunityMatrixCard clusters={clusters} />
</div>

<div style={{ padding: "20px 28px 0" }}>
  <ClusterForceGraph ... />   {/* topic cluster map */}
</div>
```

Import follows the existing `./opportunity-matrix-card.js` pattern.

### 3. Types

Consume the regenerated `@ei-fe/api` types from PR4 (no new fetch — reuse
`useMorningClusters`). If a shared shape is needed, extend the existing cluster
summary type rather than duplicating.

## Tests / verification

- FE lint + typecheck (`bun`/vite toolchain) pass.
- `/run` skill (or `docker compose up frontend`) → card renders above the map,
  counts match the API, opportunity highlighted.
- Cross-feature import rule respected (no imports from other `features/*`).

## Acceptance criteria

- Card visible above the topic cluster map on `/morning`.
- Quadrant counts reconcile with the morning cluster list.
- No legacy global CSS classes in the new component.

## Rollback

Remove the component + its placement in `morning-view.tsx`. No API/contract
impact.
