# Decision Log

This file records every non-obvious architectural and tooling decision made for Editor Intelligence. Each entry follows the format:

- **Context** — what problem prompted the decision
- **Options** — what was considered
- **Decision** — what was chosen
- **Rationale** — why
- **Implication** — what this means for future work

When rejected options would otherwise look reasonable, the entry exists to prevent re-litigation. If you want to revisit a decision, do so explicitly and update this file.

---

## D1. Modular monorepo via uv workspaces

**Context.** The project has clearly separable concerns (RSS ingestion, embedding, clustering, LLM labeling, scoring, API serving) with very different dependency profiles. Some need torch and transformers; others need only httpx.

**Options considered.**
- Single Python package, modular by folder
- uv workspace with one package per concern
- Microservices, one repository per service
- Single package with conditional / lazy imports to control deps

**Decision.** uv workspace with one package per concern.

**Rationale.** Workspace forces dependency declarations between packages, which prevents accidental coupling. The `api` package can omit torch entirely, producing a ~200MB Docker image instead of 5GB. Microservices were rejected as premature: one VPS, one user persona, one batch job per day does not justify network boundaries.

**Implication.** Adding new logic requires choosing a module. New cross-cutting concerns (logging conventions, base classes) belong in `core`. Splitting `core` itself is a discussion-worthy event.

---

## D2. src layout for every package

**Context.** Python packages can be laid out as flat (`packages/foo/foo/__init__.py`) or src (`packages/foo/src/foo/__init__.py`).

**Options considered.**
- Flat layout
- src layout

**Decision.** src layout for every package in the workspace.

**Rationale.** With src layout, tests cannot import the package via the current working directory; the package must be installed first (`uv sync`). This guarantees the test target matches the install target. Flat layout often masks packaging bugs that only surface on first deploy.

**Implication.** All `pyproject.toml` files declare `src/` as the package root. Tests live outside `src/`. This adds one directory level — that is the only cost.

---

## D3. PostgreSQL with pgvector, no separate vector DB

**Context.** The system stores dense embeddings and needs to retrieve them by cluster, by article ID, and (eventually) by similarity.

**Options considered.**
- pgvector inside the existing Postgres
- Qdrant, Milvus, Weaviate, or Pinecone as a separate service

**Decision.** pgvector inside Postgres.

**Rationale.** At this scale (tens of thousands of vectors over a 30-day window), pgvector is fast enough. A separate vector DB doubles operational surface, requires its own backup strategy, and adds a network hop to every cluster query. The team is one or two engineers; a second data store would be a recurring source of incidents.

**Implication.** Vector dimension is a column-level constraint, not a runtime constraint. Switching dimensions requires schema migration. ANN indexes (HNSW / IVFFlat) are deferred until a similarity-search feature requires them.

---

## D4. Single fixed embedding dimension, migrate on model change

**Context.** Embedding models can change (different model families, different dimensions). pgvector requires a fixed dimension per column.

**Options considered.**
- Multiple typed columns (`emb_768`, `emb_1024`)
- Per-model tables (`article_embedding_v1`, `article_embedding_v2`)
- Single column with fixed dimension; migrate when changing model
- Single dimensionless column without ANN index support

**Decision.** Single fixed-dimension column. Currently `vector(768)` matching `google/embeddinggemma-300m`.

**Rationale.** Embeddings from different model spaces are mathematically incomparable; you would never query across them. Therefore only one model is "active" at a time. When switching models, you must re-embed everything anyway, so a schema migration adds no real cost.

**Implication.** A/B testing of embedding models happens offline in notebooks, not in production schema. Provenance is preserved via `article_embedding.model_name` and `model_version` columns. The `article_embedding` table has a unique constraint on `article_id` to enforce one-active-embedding-per-article.

---

## D5. LLM (small Gemma) for cluster labels, not c-TF-IDF

**Context.** Cluster labels are the primary UI surface in the dashboard. PRD Section 7 open question #2 flagged label quality as a launch risk.

**Options considered.**
- c-TF-IDF (top-keyword extraction)
- Small local LLM (Gemma 2B class)
- Larger LLM via external API (OpenAI, Anthropic)

**Decision.** Small local LLM, with c-TF-IDF reserved as a fallback if quality is unacceptable for Bahasa Indonesia output.

**Rationale.** c-TF-IDF outputs bag-of-words ("beras, harga, premium, kg, naik") that force the editor to mentally translate keywords into topics. The dashboard's whole value proposition is reducing decision time from 1 hour to 15 minutes; bag-of-words labels reverse that gain. A small LLM produces "Lonjakan harga beras premium Q2 2026" — directly readable. Cost is ~5-10 minutes added to the daily batch, acceptable.

External APIs were rejected to keep operational scope inside the team's control and avoid a paid dependency on a foreign service for a daily batch task.

**Implication.** Labels are non-deterministic across model upgrades. Use `temperature=0` for reproducibility within a single model version. Bahasa Indonesia output quality must be validated with a 1-day spike on 5 sample clusters before committing to the chosen model.

---

## D6. `llama-cpp-python` with GGUF, not HuggingFace transformers or Ollama

**Context.** Local LLM serving has multiple options. The original plan was `transformers` directly. CPU performance validation showed that PyTorch CPU inference for Gemma 2B — even with bitsandbytes 4-bit (`nf4`) — runs 5–30 s per cluster label. At ~30 clusters per daily run that is 5–15 minutes, and bitsandbytes `nf4` has no AVX2 or Metal acceleration path.

**Options considered.**
- Ollama as a sidecar service
- `transformers` + `bitsandbytes` called directly in the pipeline process
- `llama-cpp-python` with GGUF models

**Decision.** `llama-cpp-python` with GGUF `Q4_K_M` quantization, embedded in the pipeline Python process.

**Rationale.** `llama-cpp-python` is a thin Python binding over `llama.cpp`, which is written in C++ and uses SIMD (AVX2 on x86, NEON on ARM) and Metal acceleration on Apple Silicon. For the same Gemma 2B model and comparable quantization depth, it runs 3–5× faster than PyTorch CPU inference with no GPU requirement. `Q4_K_M` is the recommended quantization level: K-quants assign different bit widths per tensor type (better quality/size than uniform quantization), and the `M` (medium) variant preserves output quality better than `S` for short multilingual text — relevant because Bahasa Indonesia is lower-resource and label quality is the primary UI surface (D5). On-disk size is ~1.6 GB; runtime RAM ~2 GB.

Dropping `transformers`, `bitsandbytes`, and `accelerate` from the `labeling` package also removes ~3 GB from the pipeline Docker image. `torch` is retained because `sentence-transformers` (embedding) requires it as a backend.

Ollama remains rejected: it adds a separate sidecar service and HTTP overhead for a batch-only, single-consumer workload.

**Implication.** The active GGUF model is `bartowski/gemma-2-2b-it-GGUF` (`gemma-2-2b-it-Q4_K_M.gguf`). `llama_cpp.Llama.from_pretrained` downloads and caches it to `settings.hf_home`. If label quality in Bahasa Indonesia proves marginal after validation, test `Q5_K_M` (slightly larger, ~2.0 GB disk, ~2.4 GB RAM) as the next step up before changing the model family. If labeling ever moves to a real-time multi-consumer pattern, revisit Ollama at that point.

---

## D7. GSC metrics retained but reference-only

**Context.** `article_gsc_metric` was in the original schema, but PRD Section 6 explicitly excludes internal article performance metrics from the UI.

**Options considered.**
- Drop the table entirely
- Keep the table, never read it (cold storage)
- Keep the table, read for scoring only (reference)

**Decision.** Keep the table. Use it as a scoring input only (e.g., to flag underperforming Tempo articles as rewrite candidates per PRD Section 1). Never return its contents in API responses.

**Rationale.** PRD Section 1 names "topics that have been written but underperformed" as rewrite candidates. GSC data feeds that signal. Section 6's prohibition is on **displaying** raw metrics in this app, not on using them as derived inputs.

**Implication.** Any field on `cluster_insight` derived from GSC (e.g., `internal_underperformed`) is allowed. Direct exposure of clicks, impressions, CTR, or position via the API is not.

---

## D8. Google Trends as separate table, articles flow normally

**Context.** Google Trends data has two parts: a trending keyword with traffic, and the articles surfaced under that keyword. The original schema treated Trends as a `source_type` value, implying its articles would live in `article` with a virtual source.

**Options considered.**
- Trends articles in `article` with `source_type='trends'` and trend metadata in nullable columns
- A separate `trend_signal` table; articles still in `article` with their real outlet as source; link via `trend_signal_article` join
- Trends consumed at runtime without persistence

**Decision.** Separate `trend_signal` table for keyword + traffic. Articles flow into `article` with their real outlet (detik, kompas, etc.) as source. `trend_signal_article` links them.

**Rationale.** Trends is a discovery channel, not a source of authorship. Articles surfaced by Trends are still authored by detik, kompas, etc. Forcing trend metadata into nullable columns on `article` was an over-fit; keeping the trend keyword as its own entity matches the domain model and leaves room for richer trend metadata (region, related queries) without polluting `article`.

The user initially considered the simpler "two nullable columns on article" approach for minimalism, but chose the separate-table model because (a) it admits richer information without schema churn and (b) it correctly positions Trends as a different conceptual entity than articles.

**Implication.** The ingest job has three coordinated writes per trend: insert `trend_signal`, insert articles, insert `trend_signal_article` rows. Wrap them in a transaction. The `trends` value was removed from `source_type`.

---

## D9. Cron-driven pipeline, no queue system

> **Status: Superseded by D24 (2026-05-03).** OS-level `cron` has been replaced by an in-process `asyncio` scheduler inside the merged `pipeline-daemon`. The "no queue system" stance still holds — see D24 for the current orchestration model. Kept for historical context.

**Context.** The daily batch pipeline runs once at 06:00 WIB and processes the day's data sequentially.

**Options considered.**
- OS-level cron / systemd timer
- APScheduler in a long-running Python process
- Celery + Redis or RabbitMQ
- Prefect or Dagster

**Decision.** OS-level cron (in production) or systemd timer. The Python application exposes CLI commands; the OS invokes them.

**Rationale.** The workload is one job per day, deterministic, sequential. A queue system adds two services (broker + worker) and a deployment pattern (workers, retries, dead letter queues) that solve no current problem. Cron failures are visible in journald; that is sufficient observability for one daily job.

**Implication.** Orchestration logic lives in the `pipeline` module's CLI. If the pipeline ever needs to run multiple times per hour or coordinate parallel work across machines, this decision is revisited.

---

## D10. No authentication in this codebase

**Context.** The dashboard is internal to Tempo. Authentication is required by policy, but not by this team.

**Options considered.**
- Build minimal auth (JWT, session cookies) into the API
- Trust an upstream gateway / reverse proxy
- Defer auth entirely (no incoming auth contract)

**Decision.** Trust an upstream gateway. The API has no auth code.

**Rationale.** Tempo's infrastructure team owns SSO and gateway concerns and will route traffic through their existing identity layer. Building auth in this app would either duplicate or conflict with that.

**Implication.** Local development runs with no auth. Production traffic is assumed to be pre-authenticated. The API may inspect a header (e.g., `X-User-Email`) for personalization, but does not validate identity itself.

---

## D11. Dockerfile and docker-compose at repository root

**Context.** Docker-related files can live at repo root or in a `docker/` subfolder.

**Options considered.**
- `docker/Dockerfile` and `docker/docker-compose.yml` (subfolder)
- `Dockerfile` and `docker-compose.yml` at repo root

**Decision.** Root-level.

**Rationale.** `docker compose up` works from the project root without `-f` flags or path tricks. Build context is intuitive (`context: .`). Standard Python and Node convention. CI tooling (GitHub Actions, etc.) defaults to root paths. Subfolder organization adds friction for every developer for marginal aesthetic gain.

**Implication.** Multi-stage Dockerfile contains `api`, `ingest`, and `pipeline` targets (each with `*-dev` variants for bind-mount development). `docker-compose.yml` is the dev composition. `docker-compose.prod.yml` is the prod composition, included from `backend/docker-compose.prod.yml`. Prod loads env from `backend/.env.prod` (gitignored); only `backend/.env.prod.example` is committed. Prod refuses to start without `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD`, binds the API to `127.0.0.1:8000` (assumes a reverse proxy in front), does not expose Postgres to the host, and runs every service with `restart: always` and rotated `json-file` logs.

---

## D12. Modular monorepo for the frontend, mirror of the backend

**Context.** The frontend is a small read-only SPA with three routes and four endpoint dependencies. It could live as a single flat package or as a workspace of packages.

**Options considered.**
- Single Vite project, all source under `frontend/src/`
- Vite project with feature folders but no package boundaries
- Bun workspace with multiple packages under `frontend/packages/` (mirror of `backend/`)
- A separate repository for the frontend

**Decision.** Bun workspace under `frontend/packages/` with five packages: `@ei-fe/core`, `@ei-fe/api`, `@ei-fe/ui`, `@ei-fe/features`, `@ei-fe/app`. Same conventions as the backend uv workspace.

**Rationale.** Package boundaries enforce dependency rules that folder structure cannot. `@ei-fe/ui` cannot accidentally import from `@ei-fe/api` because the dependency is not declared in `package.json`. This is the same reasoning behind the backend's modular split (D1). The frontend also benefits from a clear path to embedding individual packages elsewhere — e.g. importing `@ei-fe/ui` and `@ei-fe/features` into a future Next.js host without dragging the entire SPA along.

A separate repository was rejected because the frontend has no consumers outside this product, and a single repo keeps the API contract diff visible alongside FE changes that respond to it.

**Implication.** Adding new code requires choosing a package. Cross-cutting concerns belong in `@ei-fe/core`. Splitting `@ei-fe/core` is a discussion-worthy event. New packages must justify their existence beyond "feature folder" — three routes do not warrant a package per route.

---

## D13. Vite SPA, not Next.js, despite Next.js being on the long-term roadmap

**Context.** The dashboard is internal, served behind an upstream gateway, and renders no public content. Next.js was discussed as the target for a future embedding scenario.

**Options considered.**
- Next.js App Router from day one
- Vite SPA with a planned migration to Next.js
- Vite SPA with no migration planned

**Decision.** Vite SPA at MVP. Codebase structured so that a future Next.js migration is bounded to a single package (`@ei-fe/app`).

**Rationale.** Next.js adds SSR, file-system routing, and a deployment model that the product does not require at MVP. There is no SEO, no public surface, no edge rendering need. Auth lives upstream (D10). Choosing Vite reduces build complexity and keeps the dev loop fast.

Forward-compat with Next.js is preserved by isolating Vite- and React-Router-specific code to `@ei-fe/app`. The other four packages are framework-agnostic and reusable in a Next.js App Router project unchanged, modulo `"use client"` directives. Migration cost is bounded to routes, providers, and entry — estimated 1–2 days for the three MVP routes.

**Implication.** Code that touches `window`/`document` must only do so inside `useEffect` or event handlers, to remain SSR-safe for a future migration. This is enforced by review, not tooling. If Next.js becomes a requirement (embedding into another property, SEO need), the migration is a planned project, not an emergency.

---

## D14. Tailwind v4 + shadcn/ui (vendored), not vanilla CSS or CSS-in-JS

**Context.** The prototype `template-fe/` uses a single hand-written `styles.css` with custom class names. The production frontend needs a styling layer that scales beyond a single designer's stylesheet.

**Options considered.**
- Vanilla CSS or CSS Modules, port `template-fe/styles.css` directly
- styled-components / Emotion / vanilla-extract
- Tailwind v3 or v4 with custom primitives
- Tailwind + shadcn/ui (vendored components)

**Decision.** Tailwind v4 with shadcn/ui components vendored into `@ei-fe/ui/src/primitives/`.

**Rationale.** shadcn is the modern React baseline for accessible primitives — Radix UI underneath, owned source code on top, no runtime dependency on a component library. It eliminates the need to hand-build `Button`, `Tooltip`, `Dialog`, `Sheet`, `Skeleton`, `Table`, etc. with correct keyboard and ARIA behavior. Tailwind is its required pairing.

Vanilla CSS was rejected because the design system must drive type-safe component variants (variant API via `class-variance-authority`); Tailwind plus shadcn delivers this without a parallel CSS-in-JS runtime. styled-components was rejected because adding a runtime CSS engine on top of Tailwind is duplicate machinery.

**Implication.** Design tokens live once in `@ei-fe/core/src/tokens.ts`, are consumed by `@ei-fe/ui/tailwind.preset.ts`, and are mirrored manually as CSS custom properties in `@ei-fe/app/src/styles/globals.css`. shadcn components are vendored, not imported — they are part of this codebase and modified as needed. The original `template-fe/styles.css` is mined for token values, then discarded.

---

## D15. Bun workspace and `bun test`, not pnpm + Vitest

**Context.** Frontend tooling has multiple stable choices for package manager and test runner. The defaults of late-2020s React projects are pnpm + Vitest.

**Options considered.**
- npm + Jest
- pnpm + Vitest
- Bun (package manager) + Vitest
- Bun (package manager and test runner)

**Decision.** Bun for both package management and testing. Vitest reserved as a fallback if React Testing Library compatibility breaks under `bun test`.

**Rationale.** Bun's workspace and install speed exceed pnpm's at our scale. Its built-in test runner removes one dependency layer. The project has one engineer, mainstream FE deps, and no native modules — the cases where Bun's compatibility matters less commonly bite. Consolidating on one tool reduces the surface for tooling drift.

The fallback to Vitest exists because React Testing Library has historically had edge cases under non-Jest runners. If `bun test` blocks productive work, switch to Vitest with a single config file change; nothing in the codebase is Bun-specific outside of script invocation.

**Implication.** All scripts run via `bun run`. Tests run via `bun test`. The team must accept that some tooling guides assume `pnpm` and require translation. The lockfile is `bun.lock`. Docker images that need Node toolchain steps install Bun directly rather than Node + pnpm.

---

## D16. OpenAPI-driven type generation, output committed to the repo

**Context.** The FE consumes four BE endpoints. Without a binding between BE response shapes and FE types, drift is silent and surfaces as production bugs.

**Options considered.**
- Hand-written TypeScript types mirroring Pydantic models
- `openapi-typescript` codegen, run in CI, output gitignored
- `openapi-typescript` codegen, run manually, output committed
- A shared type package consumed by both BE and FE (rejected — language boundary)

**Decision.** `openapi-typescript` codegen. Developers run `bun run gen:api` against a running backend; the output `packages/api/src/generated.ts` is committed.

**Rationale.** Hand-written types drift the moment a BE engineer adds a field. Auto-generation closes that gap. Committing the output (instead of regenerating in CI) means schema changes appear as a reviewed diff in pull requests, the same way `alembic` migrations do for the BE schema (the `conventions.md` workflow). This makes the API contract explicit and auditable.

Runtime Zod schemas in `packages/api/src/schemas.ts` are maintained separately, by hand. They guard against responses that diverge from the declared OpenAPI shape — bugs, transient data issues, version skew — that static types cannot catch. The two layers overlap deliberately.

**Implication.** When BE changes a response, the FE workflow is: regenerate, review the TS diff, update Zod schemas, update affected feature components, update MSW fixtures. CI does not call `gen:api`, so a missed regeneration shows up as type errors against stale `generated.ts` on the next FE PR — not silently in production.

---

## D17. Single design-token source in TypeScript, manual sync to CSS variables

**Context.** Design tokens (colors, spacing, typography, radii) need to be consumable by Tailwind config, runtime TS code, and shadcn primitives that expect specific CSS custom properties.

**Options considered.**
- Tokens defined only in `tailwind.config.ts`
- Tokens defined only as CSS custom properties in `globals.css`
- Tokens defined in TypeScript with a generator script that emits CSS variables
- Tokens defined in TypeScript and mirrored manually to `globals.css`

**Decision.** Tokens live in `@ei-fe/core/src/tokens.ts` (typed object). The Tailwind preset imports and consumes them. `@ei-fe/app/src/styles/globals.css` mirrors the same tokens as CSS custom properties for shadcn — by hand, in the same commit when tokens change.

**Rationale.** A typed source of truth in TypeScript covers more callers than CSS variables alone — runtime conditional class names, future visualization components, and Tailwind config all benefit from typed tokens. CSS custom properties remain necessary because shadcn primitives expect them (`--background`, `--foreground`, `--radius`, etc.).

A code generator was considered but rejected for MVP. The token surface is small (under 30 entries); a generator adds tooling for a problem that doesn't exist yet. Drift is detected by code review, and re-evaluated if it actually happens.

**Implication.** Token changes require updating both `tokens.ts` and `globals.css` in a single commit. PR reviewers check this. If drift becomes a recurring source of bugs, introduce a generator script at that point.

---

## D18. Delete `template-fe/` after migration completes

**Context.** `template-fe/` is the original visual prototype. It uses HTML + UMD React + Babel-standalone — not production-suitable. Once `frontend/` reproduces its visual surface, it has no remaining role.

**Options considered.**
- Keep `template-fe/` indefinitely as a visual archive
- Move it to a `archive/` folder
- Delete it once the production frontend is feature-complete for the three MVP routes

**Decision.** Delete `template-fe/` once `@ei-fe/app` is complete and visually matches the prototype.

**Rationale.** Two parallel "frontends" in the repo invite confusion: which is canonical, which file does the user mean. The prototype's value is consumed during the migration; afterwards it is a maintenance hazard (its CDN-loaded React will eventually 404 a version, its CSS will diverge from the production tokens). Git history preserves it for reference.

**Implication.** Removal happens at a specific point in the migration plan (`frontend.md` §15, step 9). Until that step, `template-fe/` is read-only — no edits to it are made, even if a bug is discovered. Bugs discovered in the prototype are noted and addressed in the production port.


---

## D19. Source CRUD endpoints in the API

**Context.** The frontend page `/sources/rss` lets editors add new RSS feeds at runtime. With a strictly read-only API (the original MVP rule), every new feed required a code change and a redeploy of `ingest seed`. That latency blocks the editorial workflow which can identify a new competitor feed mid-day.

**Options considered.**
- Keep the API read-only; restrict source management to `python -m ingest.cli seed` and remove the `/sources/rss` page
- Expose source management as POST/PATCH/DELETE on `/api/v1/sources`
- Build a separate "admin" service with its own auth boundary

**Decision.** Expose POST/PATCH/DELETE on `/api/v1/sources`. The rest of the API (articles, clusters, trend signals, GSC metrics) remains read-only.

**Rationale.** A separate admin service is overkill for one persona on one VPS. The CLI-only path forces a deploy on every editor request, which defeats the purpose of "internal dashboard". Constraining writes to `content_source` keeps the analytical surface (articles, clusters, embeddings) immutable from the API, which preserves the auditability of pipeline outputs.

**Implication.** `docs/constraints.md` no longer says "strictly read-only" without qualification. The constraint becomes: writes are permitted only against `content_source`. Future write requests against any other table require a new decision entry. Auth is still upstream — the API trusts callers, so the upstream gateway must restrict who can hit the source endpoints.

---

## D20. Reactive ingest via `pg_notify` — alongside the daily cron, not replacing it

> **Status: Partially superseded by D24 (2026-05-03).** The reactive trigger on `rss_source_created` and the safety-net poll loop are still the model. The standalone `ingest serve` daemon has been merged into `pipeline-daemon`; both concerns now live in one supervised process. The `pg_notify` channel and behavior are unchanged.


**Context.** D9 says the pipeline is cron-driven once a day. But under D19, an editor can add a new feed at 11:00 and would otherwise wait until 06:00 the next morning before any article from that feed appears. The product target (decisions in 15 minutes) breaks down.

**Options considered.**
- Keep cron-only; tell editors to wait until the next morning
- Replace cron with a long-running daemon that polls all sources continuously
- Keep cron for the daily pipeline; add a small `serve` daemon that listens on a `pg_notify` channel for new sources and fetches them on demand

**Decision.** Keep cron for the daily pipeline. Add a `serve` daemon (`python -m ingest.cli serve`) that listens on the `rss_source_created` channel and fetches a single source immediately on demand. The daemon also runs a periodic `_run_once` poll as a safety net so that missed notifications still get caught.

**Rationale.** Replacing cron with a continuous poller would require re-thinking the embed/cluster/label/score chain that depends on a known cutoff. Reactive ingest only needs to handle the "new source" case; it does not need to re-cluster or re-score. The `pg_notify` channel keeps the API and runner decoupled — the API does not call the runner directly. Best-effort delivery (notify failures do not 500 the API; missed notifies are caught by the next poll tick) avoids the coupling problem that motivated D9.

**Implication.** The daemon is now a second long-running process alongside the API. It must be supervised (systemd, docker-compose `restart: always`, or equivalent). The runner's in-memory blocked-source map and immediate queue are process-local — running multiple replicas would cause duplicate fetches, so deploy as a singleton. Future write endpoints that should also reactively trigger a pipeline step must declare their own `pg_notify` channel, never call the runner in-process.

---

## D21. D3 for cluster force-directed graph

**Context.** The morning view needs a spatial overview of how clusters and their member articles relate to each other so editors can quickly assess groupings before drilling into detail. A plain table gives no spatial context.

**Options considered.**
- Full network-graph library (Sigma.js, Cytoscape.js, react-force-graph, vis-network)
- D3 force simulation used directly in a single component
- Plain SVG with hand-rolled force physics
- No visualization — table only

**Decision.** D3 force simulation (`d3-force`, `d3-zoom`, `d3-drag`) used directly in `@ei-fe/features/morning/cluster-force-graph.tsx`.

**Rationale.** Full network-graph frameworks (Sigma, Cytoscape) ship richer APIs than needed for one visualization and impose their own rendering model that complicates integration with React refs. D3's force simulation module is the de-facto standard for custom force-directed graphs; it provides exactly the physics, zoom, and drag primitives required without a parallel DOM abstraction. Plain SVG would require re-implementing force physics from scratch. D3 is scoped to one component — the rest of the FE does not depend on it.

**Implication.** `d3: ^7.9.0` is a dependency of `@ei-fe/features`. General-purpose charting libraries (Recharts, Chart.js) and full network-graph frameworks remain forbidden. Future visualization work that requires a different library must add a decision entry before introducing it.

---

## D22. Manual pipeline trigger endpoints

> **Status: Partially superseded by D24 (2026-05-03).** The `cluster-label-score` trigger endpoint and its `pg_notify` channel are retained. The `ingest-embed` trigger endpoint has been removed — ingest+embed is now fully reactive via the daemon's poll loop and the `rss_source_created` channel. The single `pipeline-daemon` (formerly `pipeline serve`) has absorbed `ingest serve` per D24.

**Context.** The daily cron at 06:00 WIB is the primary pipeline driver (D9). Two operational needs arose that cron cannot cover: (1) after adding a new source mid-day via D19/D20, the embedding and clustering steps still run only the next morning — articles from the new source are not clustered until then; (2) engineers debugging a clustering or labeling issue need to re-run a specific phase without waiting for the next cron window or running the full pipeline from the CLI.

**Options considered.**
- Add CLI-only re-run (no API change) — requires SSH access; not accessible to editors
- Call pipeline functions in-process from the API — violates D1; api package would import ML modules, bloating the container
- Separate HTTP admin service with its own auth boundary — overkill for one VPS, same reasoning that rejected a separate admin service in D19
- `pg_notify` to a new long-running `pipeline serve` daemon — consistent with D20 pattern; API stays lean

**Decision.** Two new endpoints, `POST /api/v1/pipeline/ingest-embed` and `POST /api/v1/pipeline/cluster-label-score`, that check a DB-level lock and send `pg_notify` to a new `python -m pipeline.cli serve` daemon. The daemon listens on both channels and runs the requested group sequentially. Single daemon handles both groups to keep supervision simple and prevent concurrent RAM spikes.

**Rationale.** The `pg_notify` pattern is already established by D20 — the API fires a notification and does not call the runner directly. The daemon holds all ML imports; the `api` package remains lean. A single daemon for both groups means state is in one process: if Group A is running, a Group B request also returns 409 without needing cross-process coordination. The DB lock row (checked by the API before notifying) is the source of truth for concurrency — it survives a daemon restart mid-run, where an in-memory flag would not.

**Implication.**
- `python -m pipeline.cli serve` is a new long-running process alongside `api` and `ingest serve`. Must be deployed as a singleton and supervised with `restart: always`.
- A new table or DB mechanism (e.g., `pipeline_group_lock`) tracks which group is currently running. The API reads this before sending `pg_notify`.
- The write-side constraint from D19 is extended: the API may now also send pipeline trigger notifications. No data table other than `content_source` and the lock mechanism is written via the API.
- `pg_notify` is best-effort: if the daemon is not running, the trigger is silently lost. There is no safety-net poll — this is intentional for a manual trigger (the caller sees `notified: true/false` in the response and can retry).
- Future pipeline groups must declare their own channel and be added to both this decision and the API contract.

---

## D23. Hardening track via four targeted SOPs (post-MVP)

**Context.** MVP is shipped. Post-MVP work is hardening (production-grade error handling, observability, idempotency, container hygiene). Until now, Docker rules lived in one sentence in `tech-stack.md` and one sentence in this file (D11), logging conventions lived only in `core/logging.py`, runtime supervision was undocumented, and "harden feature X" had no rubric. AI agents and humans had no reproducible standard.

**Options considered.**
- A single monolithic `hardening.md` covering Docker, logging, ops, and the checklist together.
- Inline expansions of `architecture.md`, `tech-stack.md`, and `conventions.md` to absorb the new content.
- A separate ops/ subfolder with its own README.
- Four targeted SOPs at the same level as `review-sop.md`, listed in the required reading order.

**Decision.** Four targeted SOPs in `docs/`, mirroring the structure of `review-sop.md`:

- `docs/docker-sop.md` — image build, layer cache, runtime hardening, compose conventions.
- `docs/logging-sop.md` — JSON logging contract, levels, structured fields, request-ID propagation.
- `docs/operations-sop.md` — running the stack in Docker, daemon supervision, recovery procedures.
- `docs/hardening-sop.md` — checklist for "harden feature X" tasks (boundaries, idempotency, observability, failure modes, resource bounds, Docker, tests).

All four are added to the required reading list in `docs/README.md`. Two new hard rules are added to `CLAUDE.md`: local dev runs in Docker; all logs go through `core.logging.configure_logging()`.

**Rationale.** Each SOP governs a distinct concern with its own audience and review trigger. A monolithic hardening doc would either be unreadable (one of every four sections matters per change) or under-specified (compressing four standards into one). Inline expansion would bloat `architecture.md` and `tech-stack.md` past their purpose; those docs answer "what is the system" and "what libraries did we choose", not "how do you operate it". A subfolder hides the docs from the canonical reading list, which defeats the goal of making hardening rules first-class citizens that AI agents must read.

The `review-sop.md` precedent already proved that a focused, opinionated, AI-and-human-targeted SOP changes contributor behavior more than scattered conventions. Replicating that shape four times preserves the proven pattern.

The two new hard rules in `CLAUDE.md` are deliberately scoped: Docker-only dev (parity) and logging-via-core (consistency). They do not mandate the full SOP content — they ensure the SOPs are surfaced on every session and the most common drift is prevented at the rule level.

**Implication.**
- Existing one-line mentions of Docker and logging in `architecture.md` and `tech-stack.md` are replaced with cross-refs; the SOPs are the single source of truth.
- Open hardening tasks (as of 2026-05) — each is the source of truth in its respective SOP, not duplicated here:
  - API logging drift — see `docs/logging-sop.md` §"Known drift to fix".
  - Frontend `Dockerfile` `prod` target — see `docs/docker-sop.md` §"Frontend Dockerfile (known issue)".
  - Backend runtime stages running as root — see `docs/docker-sop.md` §"Required runtime hardening".
  - Missing healthchecks on `api`, `pipeline-daemon` — see `docs/docker-sop.md` §"Healthchecks". (D24 removed `ingest-worker`.)
- New hardening PRs follow `docs/hardening-sop.md`: title `harden(<module>): ...`, body includes the seven-row checklist table.
- Future SOPs (security, performance) are added at the same `docs/` level if and only if they meet the same bar: distinct concern, distinct audience, distinct review trigger. Adding a fifth or sixth SOP without that justification is itself a scope expansion to question.

---

## D24. Replace OS cron with a daemon-internal scheduler; merge ingest serve into pipeline-daemon; disable scoring; tighten cluster window

**Context.** D9 chose OS-level `cron` to fire `python -m pipeline.cli run-daily` once at 06:00 WIB. Two pressures broke that model:

1. The daily cron was the only thing driving ingest+embed at scale, but D20 had already added a reactive `ingest serve` daemon that polled continuously and fetched new sources on demand. The cron's ingest pass became redundant work that ran 23 hours late.
2. Editors needed to re-cluster mid-day after correcting source data or adding a feed. D22 added two manual API endpoints (`/pipeline/ingest-embed`, `/pipeline/cluster-label-score`), but the ingest-embed trigger duplicated what the reactive daemon was already doing.

Operational complaints crystallized the issue: cron at 06:00 was "too slow, doesn't answer the actual question, and is limited to once a day". The 30-day cluster window was producing topics that no longer matched the editorial cycle. Scoring outputs (velocity, novelty, coverage) were not yet trusted enough to surface to editors.

**Options considered.**
- Keep OS cron + reactive ingest serve as-is and just tighten the cluster window. Lowest churn but does not fix the freshness or the duplicated ingest paths.
- Pure-reactive cluster trigger (cluster fires whenever new embeddings arrive). Removes scheduling but causes unstable cluster IDs visible to editors mid-read; cluster+label is ~5 min and would fire dozens of times per day.
- Stale-threshold poller (daemon checks `cluster_run.created_at` and fires when older than N hours). Self-healing if the daemon restarts, slightly more code.
- In-process `asyncio` scheduler inside `pipeline-daemon`, fixed daily tick at 06:00 WIB, with the existing manual trigger endpoint preserved for on-demand re-cluster.

**Decision.**
1. Drop OS-level `cron`. The daily 06:00 WIB cluster+label run is fired by an `asyncio` scheduler task inside `pipeline-daemon`. The same `pg_notify` channel (`pipeline_cluster_label_score_requested`) is shared by the scheduler and the manual API trigger; the runner sees one execution path.
2. Merge `ingest serve` into `pipeline-daemon`. The polled ingest loop (D20's `_run_once` + `_listen_for_new_sources`) moves into the same Python process that owns the cluster scheduler. After each ingest cycle the daemon invokes `embedding.pipeline.run` directly, not via `pg_notify` — the embed step is no longer addressable from outside.
3. Remove `POST /api/v1/pipeline/ingest-embed`. Ingest+embed is fully reactive and has no manual trigger. Drop the `pipeline_ingest_embed_requested` and `pipeline_embed_requested` channels.
4. Keep `POST /api/v1/pipeline/cluster-label-score`. Endpoint name is preserved for FE compatibility; inside the daemon, the `score` step is skipped (see #5).
5. Disable the `scoring` step. The daemon's run path no longer calls `scoring.pipeline.run`. The package, ORM models, `cluster_insight` table, and CLI entry remain untouched; existing rows are kept for reference. Re-enabling requires a future decision entry.
6. Tighten `clustering_window_days` from 30 to 7. Topics now reflect the current week.

**Rationale.** The architecture had already drifted to a daemon-driven model in practice — D20 + D22 + the embed-after-ingest commit (`ecb3d32`) covered ~80% of the work. Cron was the leftover ceremony. Pulling the schedule into the daemon removes one operational surface (host cron / systemd timer), keeps timezone handling inside Python (`settings.timezone`), and lets the same `pg_notify` channel serve both scheduled and manual runs.

A pure-reactive cluster trigger was rejected because cluster+label takes ~5 minutes and would fire on every ingest tick, producing unstable cluster IDs that editors actively reference during the morning. A stale-threshold poller is functionally equivalent to the chosen scheduler at the chosen cadence (daily) but adds a config dimension (the threshold) that has no current use case. Plain `asyncio` scheduling is the smallest viable mechanism; APScheduler / Prefect / Dagster were rejected per the existing constraint against standalone schedulers.

Merging `ingest serve` into `pipeline-daemon` increases the daemon's image size (it already imported all ML modules under D22, so the marginal cost is httpx/feedparser deps) but reduces supervised processes from three to two. Single-replica was already mandatory; consolidation does not change that. Docker layer cache means rebuilds remain cheap when source-only changes happen.

Disabling scoring acknowledges that velocity/novelty/coverage outputs were not landing usefully in the dashboard. Keeping the package and table around (rather than dropping them) preserves the option to re-enable after model tuning without a migration.

**Implication.**
- `python -m pipeline.cli serve` is the single long-running batch process. `python -m ingest.cli serve` is removed from the deployed surface; the CLI command may stay as-is for ad-hoc operator use, but no compose service runs it.
- The `pipeline-daemon` compose service is the canonical name in both `docker-compose.yml` and `docker-compose.prod.yml`. The `ingest-worker` service is removed.
- `runner.py` in `backend/packages/pipeline/` absorbs the ingest poll loop, the `rss_source_created` listener, and the scheduler task.
- `core.config.settings.clustering_window_days` defaults to `7`. Existing `.env` files that set it explicitly to `30` should be updated.
- The OpenAPI surface drops `POST /api/v1/pipeline/ingest-embed`; FE codegen must be re-run. `GET /api/v1/pipeline/status` no longer exposes the `ingest_embed` field.
- Re-enabling `scoring` requires a new decision entry naming the criteria that justified the toggle.
- Schedule cadence (`06:00`) and timezone (`Asia/Jakarta`) are read from `settings`. Changing the schedule does not require redeployment of new code, only an env reload.
- D9 is marked superseded; D20 and D22 carry partial-supersession notes pointing here.
