# Frontend

This document describes the structure of the Editor Intelligence frontend: how packages are organized, how they depend on each other, how data flows from the API into the UI, and which conventions are mandatory. It is the FE counterpart to `architecture.md` and `conventions.md` and assumes both have been read.

The frontend is a small read-only SPA serving the three views from `prd.md` Section 4. It lives in `frontend/` at the repository root, alongside `backend/` and `docs/`.

## Philosophy

**Modular monorepo, mirror the backend.** A single `frontend/` workspace contains multiple TypeScript packages under `frontend/packages/`. Each package declares its dependencies on other packages explicitly. Cross-boundary imports that are not declared in `package.json` fail to type-check. This is the same pattern used by the Python `uv` workspace under `backend/` — same reasoning applies: forced declaration prevents accidental coupling.

**Vite SPA, not Next.js.** The dashboard is internal, served behind an upstream gateway, has no SEO need, and renders no public content. SSR adds operational and build complexity for zero product value at MVP. Forward-compat with Next.js is preserved by writing browser-portable code (see §15) — migration cost is bounded to routes, providers, and entry.

**Read-only and poll-on-focus.** No write API in MVP per `architecture.md` and `prd.md` §6. The FE does not implement claim, dismiss, or any user action that mutates server state. Refresh is manual or on-window-focus; there is no polling interval.

**One design system, vendored, not imported.** shadcn/ui components are copied into `@ei-fe/ui` and owned by this codebase. Tailwind v4 is the single styling layer. Tokens are defined once in TypeScript and consumed both by Tailwind and runtime code.

## Process topology

Single concern: a static asset bundle served by the gateway.

| Process | Lifecycle | Trigger |
|---------|-----------|---------|
| `frontend` (build artifact) | Built once per release | `bun run build` produces `packages/app/dist/` |
| `vite dev` | Local development only | `bun run dev` |

The backend `api`, `pipeline`, and `postgres` processes from `architecture.md` are unchanged. The FE only requires the `api` to be reachable.

## Packages

Five packages under `frontend/packages/`, each an installable workspace member with its own `package.json` and `tsconfig.json`.

| Package | Responsibility | Depends on |
|---------|----------------|------------|
| `@ei-fe/core` | Shared kernel: env validation, design tokens, domain types, formatters, error class | (none) |
| `@ei-fe/api` | Fetch wrapper, generated OpenAPI types, runtime Zod schemas, TanStack Query keys and hooks | `@ei-fe/core` |
| `@ei-fe/ui` | shadcn/ui primitives (vendored), layout components, state components, Lucide icon registry, Tailwind preset | `@ei-fe/core` |
| `@ei-fe/features` | Feature-level views composed from `ui` primitives and `api` hooks: morning, cluster-detail, deferred | `@ei-fe/core`, `@ei-fe/api`, `@ei-fe/ui` |
| `@ei-fe/app` | Vite SPA shell: entry, providers, router, routes, global stylesheet | all of the above |

### Dependency graph

```
core ─────┐
          │
api ──────┤
          ├──> features ──> app
ui ───────┘
```

`api` does NOT import `ui`. `ui` does NOT import `api`. UI primitives are presentational and receive props; they do not know that an HTTP layer exists. This mirrors the backend rule that `api` (FastAPI) does not import ML modules — same reason: keep dumb modules dumb so they remain testable and replaceable.

`features` is the composition layer: each feature folder pulls a query hook from `api`, renders presentational components from `ui`, and exposes a single view component to `app`. `app` is intentionally thin — its only job is wiring providers and routes. Logic that lives in `app` is a smell; lift it to `features` or `core`.

Cross-feature imports are forbidden. If `features/morning` and `features/deferred` need to share a component, that component is lifted to `@ei-fe/ui`. If they need to share logic, it is lifted to `@ei-fe/core`. This mirrors the backend rule "batch module A → batch module B is forbidden" — same reason: prevent organic coupling between sibling concerns.

## Source layout

Every package uses the `src/` layout:

```
packages/<pkg>/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts          # public API (re-exports only)
│   └── (internal files)
└── tests/                # outside src/
```

Reasoning is the same as the backend: tests can only import the package via its declared entry point, not via internal file paths. This guarantees the test target matches what consumers will import.

`packages/<pkg>/package.json` declares an `exports` field pointing only to `src/index.ts`. Imports like `from "@ei-fe/api/src/queries"` will fail. Consumers use `from "@ei-fe/api"` exclusively. This is enforced by the package boundary, not by convention.

## Stack

Listed concretely. New dependencies require a corresponding entry in `tech-stack.md` and rationale in `decisions.md` (D12–D18 cover the initial set).

### Runtime
| Item | Version | Rationale |
|------|---------|-----------|
| Bun | 1.1+ | Workspace, package manager, test runner in one. Replaces npm + pnpm + jest/vitest. |
| Node-compatible runtime | n/a | Vite and tooling run on Bun's Node-compat shim. No Node binary required. |
| TypeScript | 5.6+ (strict) | Mandatory across all packages. `noImplicitAny`, `strictNullChecks` on. |

### Build & dev
| Library | Used for | Rationale |
|---------|----------|-----------|
| `vite` 5.x | Bundler + dev server | Fast HMR, modern defaults, ecosystem. |
| `@vitejs/plugin-react` | React Fast Refresh | Standard pairing. |

### UI
| Library | Used for | Rationale |
|---------|----------|-----------|
| `react` 18 | UI runtime | Already in prototype, ecosystem alignment. |
| `react-dom` 18 | DOM renderer | Pair of React. |
| `react-router-dom` 6 (data router) | Client routing | Sufficient for 3 routes; no need for TanStack Router. |
| `@tanstack/react-query` 5 | Server cache, refetch-on-focus, retry | Replaces every reason for a global state lib in this app. |
| `zod` 3 | Runtime response validation | Guards against BE schema drift at runtime even when TS types are stale. |
| `lucide-react` | Icon set | Per-icon import, tree-shakeable, default for shadcn. |
| `tailwindcss` 4 | Styling | Token-driven utility CSS, paired with shadcn. |
| `clsx` + `tailwind-merge` | className composition | Powers `cn()` helper; standard with shadcn. |
| `class-variance-authority` | Variant API for primitives | Standard with shadcn. |

### shadcn/ui
Components are copied into `packages/ui/src/primitives/` via `bunx shadcn add <component>`. Targets are configured in `packages/ui/components.json`. Once vendored, they are owned by this codebase — modify freely. shadcn is not a runtime dependency; only its underlying Radix primitives are.

| Radix primitive | Used by shadcn components in `@ei-fe/ui` |
|-----------------|----------|
| `@radix-ui/react-tooltip` | `Tooltip` |
| `@radix-ui/react-dialog` | `Dialog`, `Sheet` |
| `@radix-ui/react-slot` | `Button` |
| (others) | added per-component as shadcn introduces them |

Only add a Radix primitive when its corresponding shadcn component is actually used in `@ei-fe/features`.

### Testing & quality
| Tool | Used for |
|------|----------|
| `bun test` | Test runner |
| `@testing-library/react` | Component testing |
| `@testing-library/jest-dom` | DOM matchers (works under bun test via setup) |
| `msw` 2 | API mocking for `@ei-fe/api` and `@ei-fe/features` integration tests |
| `eslint` + `@typescript-eslint` | Linting |
| `prettier` | Formatting |

### Codegen
| Tool | Used for |
|------|----------|
| `openapi-typescript` | Generate `packages/api/src/generated.ts` from BE's `/openapi.json` |

`generated.ts` is committed. CI does not regenerate; developers run `bun run gen:api` and review the diff in PR. This is the FE analog of the Alembic workflow described in `conventions.md`.

### Rejected

| Rejected | Reason |
|----------|--------|
| Next.js | No SSR/SEO/auth need at MVP. Migration path documented in §15 if requirements change. |
| pnpm / npm | Bun's workspace and package manager are sufficient and faster. One tool, less to maintain. |
| Vitest / Jest | `bun test` covers the same surface for this app. Fall back only if React Testing Library compatibility breaks. |
| Vanilla CSS / CSS Modules / styled-components | Tailwind + shadcn is the modern React baseline and covers all needs without two parallel systems. |
| Storybook | One desk, one engineer, ~12 components. Visual review via the dev server is sufficient. |
| Redux / Zustand / Jotai / Context for server state | TanStack Query owns server cache. Local UI state uses `useState`. |
| react-hook-form / Formik | No forms in MVP — read-only API. |
| Recharts / Chart.js / D3 | Not needed for the 3 MVP routes. Deferred until a viz feature is added to PRD. |
| `axios` / `ky` / `wretch` | Native `fetch` plus a small wrapper covers our needs. One less dependency. |
| Network visualization libraries (Sigma.js, Cytoscape, react-force-graph, etc.) | Out of MVP scope. Will be evaluated when network viz is added to `prd.md`. |
| `i18next` / `react-intl` | Single language (Bahasa Indonesia). Strings hard-coded until otherwise. |

## Naming

| Element | Convention | Example |
|---------|-----------|---------|
| File | kebab-case | `cluster-table.tsx` |
| React component | PascalCase | `ClusterTable` |
| Hook | camelCase, `use*` prefix | `useMorningClusters` |
| Constant | UPPER_SNAKE | `DEFAULT_STALE_TIME` |
| Type / interface | PascalCase | `Cluster`, `ClusterDetail` |
| Package | scoped + kebab | `@ei-fe/features` |
| Folder (feature) | kebab-case | `cluster-detail/` |
| Test file | `*.test.ts(x)` co-located in `tests/` | `cluster-table.test.tsx` |

## Cross-package imports

Two enforcement layers, both required:

1. **`package.json` `dependencies`.** A package may only `import` from packages listed in its dependencies. If `@ei-fe/ui` does not declare `@ei-fe/api`, then `import { useMorningClusters } from "@ei-fe/api"` will fail to resolve.
2. **TypeScript `paths` aliases** in `tsconfig.base.json` map `@ei-fe/<name>` to `packages/<name>/src/index.ts`. This avoids relative path noise in dev while keeping the boundary at the package level.

| From → To | Allowed |
|-----------|---------|
| Any → `@ei-fe/core` | Always |
| `@ei-fe/ui` → `@ei-fe/api` | Forbidden — UI is presentational |
| `@ei-fe/api` → `@ei-fe/ui` | Forbidden — API knows no DOM |
| `@ei-fe/features` → `@ei-fe/api`, `@ei-fe/ui`, `@ei-fe/core` | Yes |
| `@ei-fe/features/morning` → `@ei-fe/features/deferred` | Forbidden |
| `@ei-fe/app` → all | Yes — orchestrator role |
| Any package → an internal file of another package (`@ei-fe/api/src/queries`) | Forbidden — only the package entry point |

If two features need shared logic, lift it to `@ei-fe/core`. If they need shared visuals, lift to `@ei-fe/ui`. Splitting `@ei-fe/core` itself is a discussion-worthy event — open an issue before adding generic utility files.

## Routing

Three routes, plus a 404. URL is the source of truth for navigation state.

| Path | Route file | Feature view | Hook | Endpoint |
|------|------------|--------------|------|----------|
| `/` | redirect → `/morning` | — | — | — |
| `/morning` | `app/routes/morning.tsx` | `@ei-fe/features/morning` | `useMorningClusters` | `GET /api/v1/clusters/morning` |
| `/clusters/:id` | `app/routes/cluster-detail.tsx` | `@ei-fe/features/cluster-detail` | `useClusterDetail` | `GET /api/v1/clusters/:id` |
| `/deferred` | `app/routes/deferred.tsx` | `@ei-fe/features/deferred` | `useDeferredClusters` | `GET /api/v1/clusters/deferred` |
| `*` | `app/routes/not-found.tsx` | — | — | — |

Route files are intentionally thin: read URL params, call the hook, render the feature view, handle URL-derived state. All composition lives in `@ei-fe/features/*`. This keeps `@ei-fe/app` portable — if the SPA migrates to Next.js, only the route layer is rewritten.

There are no nested layouts, route loaders, or route-level data fetching. TanStack Query handles fetching at component mount.

There are no query-param filters in MVP. The PRD specifies a fixed top-10 sorted by velocity; user-tunable filters are not on the happy path.

## Data layer

### API client

`@ei-fe/api/src/client.ts` is a thin `fetch` wrapper with one job per call:

1. Prepend `VITE_API_BASE_URL`.
2. Send the request.
3. Parse JSON.
4. Validate the response shape against a Zod schema.
5. Throw `ApiError` (from `@ei-fe/core`) on non-2xx or schema mismatch, with `{ status, message, requestId }`.

No interceptors, no retry logic, no auth token handling. TanStack Query owns retry. Auth is handled by the upstream gateway per `architecture.md` and `decisions.md` D10.

### Type sources

Two complementary sources of truth:

1. **`@ei-fe/api/src/generated.ts`** — output of `bun run gen:api`, which fetches `/openapi.json` from a running backend and emits TS types via `openapi-typescript`. Committed to the repo. When BE changes the response shape, the developer runs `gen:api`, reviews the diff, and addresses TypeScript errors that surface in dependent packages. This is the FE analog of `alembic revision --autogenerate`.
2. **`@ei-fe/api/src/schemas.ts`** — hand-written Zod schemas. Validated at runtime in `client.ts`. Catches BE responses that diverge from the declared OpenAPI schema (legacy data, transient bugs, version skew). Not auto-generated — maintained alongside the response schema.

The two sources overlap deliberately: static types catch developer mistakes; runtime schemas catch data drift. Both are required.

### Query keys & cache configuration

```
clusterKeys = {
  all:      ['clusters'],
  morning:  () => [...clusterKeys.all, 'morning'],
  deferred: () => [...clusterKeys.all, 'deferred'],
  detail:   (id) => [...clusterKeys.all, 'detail', id],
}
```

Default TanStack Query config:

| Setting | Value | Reason |
|---------|-------|--------|
| `staleTime` | 5 minutes | Pipeline runs once daily at 06:00 WIB; 5-minute cache balances freshness with avoiding redundant calls. |
| `gcTime` | 30 minutes | Users navigate between routes; keep cache warm. |
| `refetchOnWindowFocus` | true | Refresh when the user returns to the tab. Replaces an explicit polling timer. |
| `refetchOnMount` | true | Re-validate stale cache on route entry. |
| `retry` | 3, exponential backoff | Default. |
| `refetchInterval` | disabled | No polling — PRD specifies once-daily refresh upstream. |

The "Refresh" button in the page header calls `queryClient.invalidateQueries({ queryKey: clusterKeys.all })`.

### Loading, error, and empty states

A single convention applied across all routes, implemented via components in `@ei-fe/ui/src/states/`:

| State | UI |
|-------|----|
| Initial load | Skeleton table (10 rows for list views, header + body skeleton for detail) |
| Refetching with prior data | Show prior data + small indicator in `StatusBar` |
| 4xx/5xx error | `<ErrorState>` with retry action that invalidates the query |
| 404 cluster (detail route) | `<EmptyState>` with copy "Cluster tidak ditemukan atau bukan dari run terbaru" + link to `/morning` |
| Empty result (morning has 0 clusters) | `<EmptyState>` with copy directing the user to the deferred view |

## Styling & design system

### Single token source

`@ei-fe/core/src/tokens.ts` is the source of truth for all design tokens — colors, spacing scale, typography, radii, shadows. It exports a typed object consumed by:

- `@ei-fe/ui/tailwind.preset.ts` — feeds `theme.extend` so utility classes match
- Runtime TS code that needs token values directly (conditional class names, future viz components)

A small hand-written CSS file in `@ei-fe/app/src/styles/globals.css` mirrors the same tokens as CSS custom properties for use in shadcn primitives (which expect `--radius`, `--background`, `--foreground`, etc.). Sync between `tokens.ts` and `globals.css` is manual at MVP — when tokens change, both files update in the same commit. Automation (a generator script) is deferred until drift is observed in practice.

### Tailwind v4

Each consumer package configures Tailwind via the preset:

```
// packages/app/tailwind.config.ts
import preset from "@ei-fe/ui/tailwind.preset"
export default {
  presets: [preset],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "../ui/src/**/*.{ts,tsx}",
    "../features/src/**/*.{ts,tsx}",
  ],
}
```

The `content` glob across workspace packages ensures Tailwind sees all classes used by `ui` and `features` even though they live outside `app/src/`.

### shadcn/ui

shadcn is a CLI that copies component source into your codebase. It is configured per `@ei-fe/ui/components.json` with target paths inside `packages/ui/src/primitives/`. Vendored components are then exported from `@ei-fe/ui` and consumed by `features` and `app`.

```
cd packages/ui
bunx shadcn add button
bunx shadcn add table
```

After vendoring, modify components freely. They are part of this codebase, not an external dependency.

### Icons

`@ei-fe/ui/src/icons.ts` re-exports the specific Lucide icons used by the app:

```
export { RefreshCw, Filter, Plus, ChevronRight, ... } from "lucide-react"
```

This single audit point makes the icon footprint easy to inspect and prevents arbitrary `import { ... } from "lucide-react"` scattered across packages. Add new icons via this file only.

## Testing

| Level | Tool | Scope |
|-------|------|-------|
| Unit | `bun test` + Vitest-compat APIs | Pure functions in `@ei-fe/core` (formatters, env validation) and `@ei-fe/api` (schema validation, key factory) |
| Component | `bun test` + React Testing Library | `@ei-fe/ui` primitives — render, interaction, prop variants |
| Integration | `bun test` + RTL + MSW | Per-feature views in `@ei-fe/features` — mount with provider, MSW responds with fixtures, assert happy path + error + empty |
| End-to-end | not in MVP | Playwright reserved for when visual regression becomes a real risk |

Each route in `@ei-fe/features` has at minimum one happy-path integration test and one error-state test. There is no coverage threshold in CI — quality of assertions matters more than count.

`@ei-fe/api/tests/mocks/` contains MSW handlers and JSON fixtures that mirror the BE response shape. Fixtures are the de facto contract reference during FE-only development; they must be updated when `generated.ts` or `schemas.ts` change.

## Codegen workflow

Mirror of the backend's Alembic flow:

```bash
# Backend running locally on http://localhost:8000
bun run gen:api

# This:
# 1. Fetches /openapi.json
# 2. Runs openapi-typescript
# 3. Writes packages/api/src/generated.ts
# 4. Runs prettier on the output

# Review the diff, then commit
git diff packages/api/src/generated.ts
```

When BE changes the response shape:

1. Developer runs `bun run gen:api`.
2. TypeScript errors appear in dependent packages (queries, schemas, feature views).
3. Update `schemas.ts` (Zod) to match the new shape.
4. Update affected feature components.
5. Update MSW fixtures in `@ei-fe/api/tests/mocks/`.

`generated.ts` is committed. CI does not run `gen:api` — keeping it manual ensures the diff is reviewed by a human and the PR documents the contract change.

## Module development order

Bottom-up, mirroring the backend convention. Do not start a package until its upstream is functional and tested.

1. `@ei-fe/core` — tokens, env, types, formatters, error class
2. `@ei-fe/api` — client, schemas, generated types, query keys, hooks (validated against MSW)
3. `@ei-fe/ui` — Tailwind preset, shadcn primitives vendored, layout, state components, icon registry
4. `@ei-fe/features` — three feature views composed from `ui` + `api`
5. `@ei-fe/app` — Vite SPA shell, providers, routes

A package is "done" when it can be consumed end-to-end by a downstream package against real (or MSW-mocked) data, and its tests pass.

## Bun command cheat sheet

```bash
# From frontend/ root
bun install                   # install all workspace deps

# Run a script defined in a package
bun --filter @ei-fe/app run dev
bun --filter @ei-fe/api run gen:api

# Run all tests across workspace
bun test

# Build production bundle
bun run build                 # delegates to @ei-fe/app build

# Add a runtime dep to a specific package
bun add --filter @ei-fe/ui @radix-ui/react-tooltip

# Add a dev-only dep at workspace root
bun add -D prettier
```

## Build & deployment contract

- `bun run build` produces `frontend/packages/app/dist/` containing static HTML, hashed JS, hashed CSS, and font assets.
- Only `dist/` is deployed. The other workspace packages are internal and never published to a registry.
- Serving the bundle is the deploy team's responsibility (gateway, nginx, or FastAPI `StaticFiles` — outside this codebase).
- Gateway must serve `index.html` as the SPA fallback so deep links to `/clusters/:id` survive a hard refresh.
- Cache headers (immutable hashed assets, no-cache `index.html`) are an operational concern, not configured in this repo.
- `VITE_API_BASE_URL` is the single FE-side configuration. Validated by `@ei-fe/core/env.ts` at boot. Default `/api/v1` when FE and BE share an origin.

## Out of this codebase

These exist or will exist for the product but are NOT implemented in `frontend/`:

- **Authentication and identity.** Handled by the upstream gateway (`decisions.md` D10).
- **Production deployment infrastructure.** Static assets are output; serving them is the deploy team's concern.
- **Backend.** Lives in `backend/`. The contract is the JSON shape of the four API endpoints.
- **Monitoring stack.** Browser-side errors and analytics are not collected in MVP. If they become a requirement, evaluate Sentry or equivalent at that point.
- **Internal article performance metrics in any UI form.** `constraints.md` is authoritative — never display GSC clicks, impressions, CTR, or position.

## Out of MVP scope

Deferred until added to `prd.md` or `decisions.md`:

- Network / topic visualization (Sigma.js, Cytoscape, react-force-graph). Discussed in conversation but not in PRD; pending product decision.
- Charts of any kind (no charting library is installed).
- Manual claim or dismiss actions on clusters (PRD §6).
- Cluster lineage / time-series views (PRD §6).
- Push notifications, in-app notifications, toast streams.
- Internationalization. Strings are Bahasa Indonesia, hard-coded.
- Theme switching. One palette, light mode, lock.
- User preferences, saved filters, dashboards. No persistence layer beyond TanStack Query cache.
- Storybook or any component-isolation environment.

If a feature request implies any of the above, surface the conflict with `constraints.md` and `prd.md` §6 before implementing.

## Migration from `template-fe/`

`template-fe/` is the original prototype: HTML + UMD React + Babel-standalone. It is the visual reference for the production FE but not the source of any production code.

Migration steps:

1. Bootstrap `frontend/` workspace (this document is the spec).
2. Port `template-fe/styles.css` tokens (colors, spacing, typography) into `@ei-fe/core/src/tokens.ts` and `@ei-fe/app/src/styles/globals.css`. Discard the rest of `styles.css`.
3. Port the `Sidebar`, `StatusBar`, and page-head layout from `template-fe/components.jsx` into `@ei-fe/ui/src/layout/`.
4. Reproduce the `page-dashboard.jsx` visual in `@ei-fe/features/morning/`.
5. Reproduce the `page-bucket.jsx` visual in `@ei-fe/features/cluster-detail/`.
6. Build `@ei-fe/features/deferred/` (no direct `template-fe` analog — use the Morning view as a starting point).
7. Wire routes in `@ei-fe/app/`.
8. Connect to live backend, validate end-to-end.
9. **Delete `template-fe/`.** Update `docs/README.md` to remove references.

The following prototype pages are NOT ported because they correspond to features deferred per `prd.md` §6:

- `page-keywords.jsx`
- `page-buckets.jsx`
- `page-performance.jsx`
- `page-desk.jsx`
- `page-queue.jsx`
- `tweaks-panel.jsx`

## Forward-compat with Next.js

The Vite SPA is the MVP, but the codebase is structured so a future migration to Next.js is bounded in scope:

- `@ei-fe/core`, `@ei-fe/api`, `@ei-fe/ui`, `@ei-fe/features` are framework-agnostic React/TS code. They are reusable in a Next.js App Router project unchanged, modulo `"use client"` directives where needed.
- `@ei-fe/app` is the only package that depends on Vite and React Router. A Next.js migration replaces this single package.
- Browser-only APIs (`window`, `document`) must only be accessed inside `useEffect` or event handlers. This rule is enforced by code review; it has no automated check at MVP.
- TanStack Query setup follows the singleton-per-render pattern that survives Next.js's hydration model.

Migration cost estimate is low (1–2 days for the existing three routes), but is not undertaken until a concrete reason exists to use Next.js (embedding into another Next.js property, SEO requirement, edge rendering need).
