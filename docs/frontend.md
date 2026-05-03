# Frontend

This document describes the structure of the Editor Intelligence frontend: how packages are organized, how they depend on each other, how data flows from the API into the UI, and which conventions are mandatory. It is the FE counterpart to `architecture.md` and `conventions.md` and assumes both have been read.

The frontend is a small read-only SPA serving the three views from `prd.md` Section 4. It lives in `frontend/` at the repository root, alongside `backend/` and `docs/`.

## Philosophy

**Modular monorepo, mirror the backend.** A single `frontend/` workspace contains multiple TypeScript packages under `frontend/packages/`. Each package declares its dependencies on other packages explicitly. Cross-boundary imports that are not declared in `package.json` fail to type-check. This is the same pattern used by the Python `uv` workspace under `backend/` — same reasoning applies: forced declaration prevents accidental coupling.

**Vite SPA, not Next.js.** The dashboard is internal, served behind an upstream gateway, has no SEO need, and renders no public content. SSR adds operational and build complexity for zero product value at MVP. Forward-compat with Next.js is preserved by writing browser-portable code (see §15) — migration cost is bounded to routes, providers, and entry.

**Read-dominant and poll-on-focus.** The only write surface is source management — `POST/PATCH/DELETE /api/v1/sources` per `decisions.md` D19. Clusters, articles, and trend signals are read-only from the FE. Refresh is manual or on-window-focus; there is no polling interval.

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
| `@ei-fe/features` | Feature-level views composed from `ui` primitives and `api` hooks: morning, cluster-detail, article | `@ei-fe/core`, `@ei-fe/api`, `@ei-fe/ui` |
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

Cross-feature imports are forbidden. If `features/morning` and `features/article` need to share a component, that component is lifted to `@ei-fe/ui`. If they need to share logic, it is lifted to `@ei-fe/core`. This mirrors the backend rule "batch module A → batch module B is forbidden" — same reason: prevent organic coupling between sibling concerns.

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
| `d3` 7 | Force-directed cluster graph (`@ei-fe/features/morning`) | Force simulation, zoom, drag for the morning cluster visualization. See `decisions.md` D21. Do not use for other purposes without a new decision entry. |
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

What was considered and rejected lives in `constraints.md` §"Architectural don'ts (frontend)" (the "do not introduce" list) and `decisions.md` D12–D18 (the rationale). Do not duplicate here.

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
| `@ei-fe/features/morning` → `@ei-fe/features/article` | Forbidden |
| `@ei-fe/app` → all | Yes — orchestrator role |
| Any package → an internal file of another package (`@ei-fe/api/src/queries`) | Forbidden — only the package entry point |

If two features need shared logic, lift it to `@ei-fe/core`. If they need shared visuals, lift to `@ei-fe/ui`. Splitting `@ei-fe/core` itself is a discussion-worthy event — open an issue before adding generic utility files.

## Routing

URL is the source of truth for navigation state.

| Path | Route file | Feature view | Hook(s) | Endpoint |
|------|------------|--------------|---------|----------|
| `/` | redirect → `/morning` | — | — | — |
| `/morning` | `app/routes/morning.tsx` | `@ei-fe/features/morning` | `useMorningClusters`, `clusterDetailQueryOptions` | `GET /api/v1/clusters/morning`, `GET /api/v1/clusters/:id` |
| `/clusters/:id` | `app/routes/cluster-detail.tsx` | `@ei-fe/features/cluster-detail` | `useClusterDetail` | `GET /api/v1/clusters/:id` |
| `/article` | `app/routes/article.tsx` | `@ei-fe/features/article` | `useArticles` | `GET /api/v1/articles` |
| `/clustering` | `app/routes/clustering.tsx` | inline (dummy data) | — (proposed: `useLatestClusterRun`) | `GET /api/v1/cluster-runs/latest` (PROPOSED) |
| `/sources` | `app/routes/sources.tsx` | inline | `useSources`, `useToggleSource`, `useDeleteSource` | `GET/PATCH/DELETE /api/v1/sources` |
| `/sources/rss` | `app/routes/input-rss.tsx` | inline | `useCreateSource` | `POST /api/v1/sources` |
| `*` | `app/routes/not-found.tsx` | — | — | — |

Route files are intentionally thin: read URL params, call the hook, render the feature view, handle URL-derived state. Routes with more complex UI (`/clustering`, `/sources`, `/sources/rss`) are self-contained inline — they do not have a dedicated feature package because they fall below the threshold warranting one. Composition-heavy views (`/morning`, `/clusters/:id`, `/article`) live in `@ei-fe/features/*`.

There are no nested layouts, route loaders, or route-level data fetching. TanStack Query handles fetching at component mount.

The only query params in v1 are `page` and `page_size` on `/article`. Other routes have no filter params.

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
  all:     ['clusters'],
  morning: () => [...clusterKeys.all, 'morning'],
  detail:  (id) => [...clusterKeys.all, 'detail', id],
}
articleKeys = {
  all:  ['articles'],
  list: (page, pageSize) => [...articleKeys.all, 'list', page, pageSize],
}
sourceKeys = {
  all:  ['sources'],
  list: () => [...sourceKeys.all, 'list'],
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
| Empty result (morning has 0 clusters) | `<EmptyState>` with copy indicating no clusters for today |

## Date / time formatting

**Display standard: WIB / Asia/Jakarta (GMT+7).** Every user-facing timestamp goes through one of the helpers in `frontend/packages/core/src/format.ts`:

| Helper | Output | Use for |
|---|---|---|
| `formatDate(iso)` | `1 Mei 2026` | Date columns in tables (e.g., article published_at, created_at) |
| `formatDateTime(iso)` | `01 Mei 2026, 23.45` | Audit timestamps, last_fetched_at, anything where minute precision matters |
| `formatTime(iso)` | `23.45` | Compact stamps inside cards (e.g., trend signal captured_at) |
| `formatRelative(iso)` | `2j lalu`, `baru saja` | "Time-since" indicators |

All helpers set `timeZone: "Asia/Jakarta"` and locale `id-ID`. Components MUST NOT call `new Date(iso).toLocaleString(...)` inline — duplicate timezone configuration drifts and the WIB defaults get lost. The only legitimate inline use is for "now" indicators (`new Date()` representing the user's current wall-clock moment), and those still need `timeZone: "Asia/Jakarta"`.

The wire format from the API is ISO-8601 UTC with the `Z` suffix — see `conventions.md` §API endpoints. The helpers tolerate strings without an explicit timezone by treating them as UTC; this is a safety net, not a contract.

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
- **Backend.** Lives in `backend/`. The contract is FastAPI's `/openapi.json` — see `conventions.md` §API endpoints.
- **Monitoring stack.** Browser-side errors and analytics are not collected in MVP. If they become a requirement, evaluate Sentry or equivalent at that point.
- **Internal article performance metrics in any UI form.** `constraints.md` is authoritative — never display GSC clicks, impressions, CTR, or position.

## Out of MVP scope

The deferred-feature list lives in `prd.md` §6 and `constraints.md` (frontend section). Do not duplicate here. If a request implies a deferred feature, surface the conflict before implementing.

## Migration from `template-fe/`

`template-fe/` is the visual reference prototype. It is read-only and will be deleted per `decisions.md` D18 once `@ei-fe/app` reproduces the three MVP views. The prototype pages that map to deferred PRD §6 features are not ported.

## Forward-compat with Next.js

The Vite SPA is the MVP, but the codebase is structured so a future migration to Next.js is bounded in scope:

- `@ei-fe/core`, `@ei-fe/api`, `@ei-fe/ui`, `@ei-fe/features` are framework-agnostic React/TS code. They are reusable in a Next.js App Router project unchanged, modulo `"use client"` directives where needed.
- `@ei-fe/app` is the only package that depends on Vite and React Router. A Next.js migration replaces this single package.
- Browser-only APIs (`window`, `document`) must only be accessed inside `useEffect` or event handlers. This rule is enforced by code review; it has no automated check at MVP.
- TanStack Query setup follows the singleton-per-render pattern that survives Next.js's hydration model.

Migration cost estimate is low (1–2 days for the existing three routes), but is not undertaken until a concrete reason exists to use Next.js (embedding into another Next.js property, SEO requirement, edge rendering need).
