# Constraints

This document is a list of things that **must not be done** in this codebase. Many of these look like obvious improvements but are deliberately deferred or out of scope. Re-introducing any of these without explicit user approval is the most common failure mode for AI agents.

When in doubt, defer.

## Out of this codebase entirely

The following systems exist for the product but are owned by other teams. Do not implement them here:

- **Authentication and authorization.** Identity is established by an upstream gateway. The API trusts incoming requests.
- **Deployment infrastructure beyond local Docker dev.** Production orchestration, scaling, secrets management, and CI/CD pipelines are owned by the deploy team.
- **Production monitoring, alerting, dashboards.** The application logs to stdout in JSON per `docs/logging-sop.md`. Aggregation, retention, and alerting are operational concerns owned externally.
- **Raw internal article performance metrics for end-user display.** A separate Tempo internal dashboard already shows clicks, impressions, and Google position. This app does not display raw GSC numbers (clicks, impressions, position, CTR). Derived editorial *levels* (`high_demand`, `performance_level`, `editorial_quadrant`) are permitted — see D35.

## Deferred features (PRD Section 6 — authoritative)

The following features were explicitly deferred during PRD review. They must not be re-introduced unless the user removes them from the deferred list:

- Raw internal article performance metrics (clicks, impressions, position, CTR) displayed in the UI — derived editorial levels are permitted per D35
- Dedicated desk-head dashboard with team metrics
- Cluster lineage / cross-time topic tracking
- Manual claim or dismiss-cluster actions in the UI
- Push notifications, Slack alerts, email notifications
- Similar-article search for writers
- Auto-categorization of content type
- Composite "worth writing" score as a single number
- Burst detection for sudden hot topics
- Per-competitor breakdown ("Detik yes, Kompas no")
- HNSW or IVFFlat vector similarity index
- Auto angle detection
- Auto premium-content scoring
- Tracking competitor view or engagement metrics

If a user request implies any of these, surface the conflict with `prd.md` Section 6 before implementing.

**Hardening work uses `docs/hardening-sop.md`.** Hardening tasks (timeouts, retries, idempotency, observability, resource bounds, container hardening, smoke tests) must not introduce features deferred above. If a hardening task uncovers a missing capability, file a separate decisions entry — do not bundle it into the hardening PR.

## Architectural don'ts

These patterns must not appear in the codebase. Each was explicitly considered and rejected; see `decisions.md` for full reasoning.

- **No microservices split.** The codebase is a modular monorepo. Modules are Python packages, not separate services.
- **No message queue (Celery, RQ, RabbitMQ, Redis Streams).** Pipeline orchestration is a singleton daemon driven by `pg_notify` plus an in-process `asyncio` scheduler.
- **No standalone job scheduler library (APScheduler, Prefect, Dagster).** Scheduling lives inside the pipeline daemon as plain `asyncio` tasks. There is no host `cron` and no `systemd timer`.
- **No Redis cache or other in-memory cache layer.** Postgres handles read load.
- **No separate vector database (Qdrant, Milvus, Weaviate, Pinecone).** pgvector is sufficient.
- **No GraphQL.** REST endpoints only.
- **No WebSockets.** The dashboard is poll-based.
- **No `nvidia-*`, `cuda-*`, or `triton` wheels in any image.** No deploy target has an NVIDIA GPU; Colima on macOS cannot pass one through, and the production VPS is CPU-only. `torch` is pinned to PyTorch's CPU index for `linux`/`win32` in `backend/pyproject.toml`. macOS host installs still use the standard PyPI wheel (Metal-capable). If a fresh `uv lock` ever reintroduces a `nvidia-*` / `cuda-*` / `triton` package, the pin is broken — fix the pin, do not accept the lock.
- **No event sourcing or CQRS.** Standard CRUD against Postgres.
- **Write-side API is restricted to two surfaces** (any addition beyond these requires a new decision entry):
  1. `ContentSource` CRUD on `/api/v1/sources` — editors manage RSS feeds at runtime (D19).
  2. Manual cluster trigger on `/api/v1/pipeline/cluster-label-score` — sends `pg_notify` to the pipeline daemon. Writes only to the `pipeline_group_lock` row and emits a notification; no analytical table is touched. Ingest and embed are fully reactive and have no manual API trigger; the previous `/api/v1/pipeline/ingest-embed` endpoint has been removed.
  Every analytical table — `article`, `cluster*`, `cluster_run`, `cluster_insight`, `trend_signal`, `article_embedding`, `article_gsc_metric` — remains read-only via the API.

## Code don'ts

- **No comments that explain WHAT the code does.** Identifier names are the documentation. Comments are for non-obvious WHY.
- **No multi-paragraph docstrings.** One-line summaries when they add value.
- **No defensive validation between trusted internal modules.** Validate at system boundaries (HTTP input, external APIs). Internal interfaces are typed.
- **No backwards-compatibility shims for code that has not been released.** The codebase is pre-1.0; refactor freely.
- **No premature abstraction.** If three call sites do similar things, leave them similar. Three is not a pattern.
- **No `try / except` that catches and re-raises with no value added.**
- **No new top-level dependencies without listing them in `tech-stack.md` and providing rationale.**

## Schema invariants

These invariants are enforced by `schema.dbml` and must be preserved:

- **`article_embedding.embedding` is `vector(768)`.** Changing dimension requires a schema migration AND a full re-embed of all articles. Do not introduce parallel dimension columns.
- **One embedding per article.** `article_embedding.article_id` is unique. Changing the embedding model means re-embedding into the same row.
- **GSC metrics are reference-only (D35).** `article_gsc_metric` rows and the raw GSC aggregate columns in `cluster_insight` (`gsc_impressions`, `gsc_clicks`, `gsc_ctr`, `gsc_avg_position`) are internal scoring inputs only — never returned in API responses. Derived editorial levels (`demand_score`, `high_demand`, `performance_level`, `editorial_quadrant`) are signals, not raw metrics, and may be returned — same category as the existing `underperformed` and `tempo_covered` booleans. The frontend has no concept of raw GSC numbers.
- **Trends are not articles.** Trend keywords live in `trend_signal`. Articles surfaced via Trends RSS go in `article` and link via `trend_signal_article`. Do not put trend keywords in `article` columns.
- **`is_current` flag on `article_cluster` is the marker of the latest run's clusters.** Flipping it must happen atomically when a new `cluster_run` finishes.
- **`source_type` enum has exactly two values: `rss` and `internal`.** Do not re-add `trends`.

## Things that look like bugs but aren't

- The PRD is short (~3 pages). Do not interpret missing details as gaps. PRD Section 6 lists what is intentionally absent.
- `article.url` is `unique` and ingest uses `ON CONFLICT (url) DO NOTHING`. The same article appearing in both a competitor RSS and Trends RSS is silently de-duplicated. This is intentional.
- `cluster_insight.summary` exists but is not currently surfaced to the API. Reserved for future LLM-generated summaries; safe to ignore for now.
- The two personas (Maulana and the desk head) use the **same** application. There is no role-based feature partitioning. They use different views of the same data.
- Cluster + label runs once per day at 06:00 WIB on the daemon's internal scheduler, plus on demand via `POST /api/v1/pipeline/cluster-label-score`. Ingest and embed run reactively whenever a new RSS source is added or the daemon's poll loop tick fires. There is no streaming and no hourly cluster refresh; clustering is the expensive step and is intentionally bounded to one daily run plus operator-driven re-runs.
- The `scoring` step is currently disabled in the daemon. The package, tables, ORM models, and CLI entry remain in place; new daemon runs do not write `cluster_insight` rows. Existing rows are kept for reference. Re-enabling scoring requires a decision entry.

## Frontend constraints

The production frontend lives in `frontend/` (Bun workspace, Vite SPA). The legacy prototype `template-fe/` is reference-only and will be deleted per `decisions.md` D18. See `frontend.md` for the full architecture.

### Out of the frontend codebase
- **Authentication.** Upstream gateway (D10). The FE never validates identity.
- **Production hosting / serving config.** `bun run build` outputs static assets; the deploy team owns gateway, nginx, cache headers, and SPA fallback.
- **Backend.** Lives in `backend/`. The contract is FastAPI's `/openapi.json` — see `conventions.md` §API endpoints.
- **Browser-side error tracking and analytics.** Not in MVP. Add only when there is a documented operational need.

### Architectural don'ts (frontend)
- **No alternative framework.** Vite SPA only at MVP. Next.js migration is a planned project per D13, not a creeping rewrite. Do not introduce Next.js, Remix, or Astro files alongside the Vite app.
- **No CSS-in-JS or alternative styling layer.** Tailwind v4 + shadcn (D14) is the only styling system. Do not add styled-components, Emotion, vanilla-extract, CSS Modules, or a parallel `globals.css` outside `@ei-fe/app/src/styles/`.
- **No state management library for server data.** TanStack Query owns server cache. Local UI state uses `useState`. Do not add Redux, Zustand, Jotai, MobX, or a global Context for server-derived data.
- **No HTTP client library.** Native `fetch` plus the wrapper in `@ei-fe/api/src/client.ts` only. Do not add axios, ky, wretch, or similar.
- **No general-purpose charting or network-graph library.** Do not add Recharts, Chart.js, Sigma, Cytoscape, react-force-graph, or vis-network. D3 is permitted only for the existing force-directed cluster visualization in `@ei-fe/features/morning/cluster-force-graph.tsx` (see `decisions.md` D21); do not introduce it in other contexts or ship new D3-heavy features without a decisions entry.
- **No auth library.** No NextAuth, Auth0 SDK, Clerk, or session helpers. Identity is upstream.
- **No form library.** No react-hook-form, Formik, or Final Form. The only write surface (source management, D19) is small enough that controlled inputs + native validation suffice.
- **No internationalization library.** No i18next, react-intl, or LinguiJS. Strings are Bahasa Indonesia and hard-coded.
- **No theme switcher.** One palette, light only. The `tweaks-panel` from `template-fe/` is designer tooling and is not ported.
- **No Storybook or component-isolation environment.** Visual review happens in the dev server.
- **No icon set besides Lucide.** Adding a second icon system is forbidden — extend `@ei-fe/ui/src/icons.ts` instead.
- **No write-side endpoints beyond source management.** Per D19 the FE has source CRUD on `/sources` and `/sources/rss`. No other mutating UI elements (no claim, dismiss, bookmark, etc.) — clusters, articles, and trend signals stay read-only.
- **No cross-feature imports inside `@ei-fe/features`.** A view in `features/morning` may not import from `features/article`. Shared visuals lift to `@ei-fe/ui`; shared logic lifts to `@ei-fe/core`.
- **No deep imports across packages.** `@ei-fe/<pkg>/src/...` is forbidden. Import the package entry point only.
- **No new top-level dependencies without listing them in `frontend.md` "Stack" and providing rationale.**

### Code don'ts (frontend)
- **No comments that explain WHAT the code does.** Same rule as the backend.
- **No `window`/`document` access outside `useEffect` or event handlers.** This rule preserves the future Next.js migration path (D13).
- **No JSX in `@ei-fe/api` or `@ei-fe/core`.** These packages are framework-agnostic.
- **No data fetching inside `@ei-fe/ui` components.** UI primitives are presentational and receive props only.
- **No `any` in declared types.** TypeScript runs in strict mode; if `any` is genuinely required, it must be local and commented with the WHY.

### Schema invariants (frontend)
- **`@ei-fe/api/src/generated.ts` is generated, not edited by hand.** It is regenerated via `bun run gen:api` from the BE's `/openapi.json`. Hand edits will be overwritten.
- **`@ei-fe/api/src/schemas.ts` (Zod) is hand-written and authoritative for runtime validation.** It must be updated alongside any change to `generated.ts`.
- **Design tokens have one source: `@ei-fe/core/src/tokens.ts`.** `globals.css` mirrors them; do not introduce a third location.

### Things that look like bugs but aren't
- The `template-fe/` directory contains pages (`page-keywords.jsx`, `page-buckets.jsx`, `page-performance.jsx`, `page-desk.jsx`, `page-queue.jsx`, `tweaks-panel.jsx`) that are NOT ported. They correspond to features deferred per `prd.md` §6.
- The FE has no polling timer. Refresh on window focus plus a manual refresh button is the entire freshness model. The pipeline runs once per day; an interval poll would do nothing useful.
- `generated.ts` is committed to git. This is intentional (D16) so schema changes appear as reviewed diffs, not silent CI artifacts.
- The two personas use the same dashboard. There is no role-based gating; auth is upstream. Both land on `/morning` as the primary entry point.
