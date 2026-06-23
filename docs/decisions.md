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

> **Status update**: D24's "scoring step is disabled" clause is **superseded by D27** (2026-05-09). Scoring is re-enabled with a redesigned `cluster_insight` shape. All other D24 decisions stand.

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

---

## D25. Full-text article scraping: trafilatura fast path + Playwright deferred fallback

**Context.** The ingest pipeline currently populates `article.first_paragraph` from RSS `<summary>` only — typically a 200–400 character excerpt stripped of HTML. Embeddings produced from this truncated text cluster weakly: semantically related articles diverge because their excerpts share no vocabulary even when their full bodies are near-identical. The root fix is to store the full article body and embed that instead.

**Options considered.**
- Keep the current excerpt-only approach
- Playwright for all URLs (always headless browser)
- `trafilatura` + `httpx` for all URLs (no browser)
- `trafilatura` + `httpx` as the primary path, Playwright only for articles that fail the fast path, executed as a deferred background worker

**Decision.** Two-phase scraping, executed in the `pipeline-daemon`:

1. **Fast path (inline, after each ingest cycle).** For every newly ingested article, attempt `httpx` fetch + `trafilatura` extraction with a 10-second timeout. On success, write to `article.content` and set `article.scrape_status = fast_ok`. On failure (network error, timeout, empty extraction), set `article.scrape_status = fast_failed` — the article enters the deferred queue implicitly.

2. **Playwright worker (deferred asyncio task in daemon).** A background `asyncio` task polls for `scrape_status = fast_failed` articles at a fixed cadence. For each batch it: launches a Playwright Chromium browser, renders the page, passes the rendered HTML through `trafilatura`, writes `content`, then closes the browser. Max 2 attempts per article. After 2 failures, `scrape_status = playwright_failed` and the article is not retried.

Both paths use `trafilatura` for extraction — output quality is consistent regardless of which path succeeds.

**Schema changes required.**
- `article.content` — `Text`, nullable. Stores the full article body. Existing articles default to `NULL`; embeddings for those articles continue using `first_paragraph` as fallback until `content` is populated.
- `article.scrape_status` — new `ScrapeStatus` enum: `pending | fast_ok | fast_failed | playwright_ok | playwright_failed`. Default `pending` on insert. Index on `(scrape_status)` to support the Playwright worker's poll query.
- Migration required (Alembic autogenerate).

**Scope constraints (firm).**
- **New articles only.** No backfill of existing rows. Articles already in the table before this feature lands keep `scrape_status = NULL` and `content = NULL`; the embedding step continues using `first_paragraph` for those.
- **Fast path timeout: 10 seconds.** Any article that does not resolve within 10 seconds via httpx is immediately moved to the Playwright queue.
- **Playwright retry cap: 2 attempts.** After two failures the article is marked `playwright_failed` and abandoned.
- **Rate limiting per domain.** The Playwright worker enforces a per-domain concurrency cap and inter-request delay to avoid hammering any single outlet. The fast path uses httpx with existing User-Agent spoofing (already in `rss.py`).
- **Browser lifecycle: launch → scrape batch → close.** The Playwright browser is not kept alive between Playwright worker ticks. This prevents resident memory pressure alongside the sentence-transformers and llama-cpp models that share the same container.

**Rationale.** Playwright-for-all was rejected because most Indonesian news sites (Detik, Kompas, Tempo, Tribun) serve full article HTML without JS rendering — a headless browser adds 4–6 s of overhead per article for no gain. `trafilatura`-only was rejected because a minority of outlets are SPA or require JS-rendered bylines. The two-phase model captures the fast case (≥85% of articles, ~0.3–0.8 s each) without surrendering coverage on JS-heavy pages.

An in-memory asyncio queue was rejected in favour of the `scrape_status` column because it does not survive daemon restarts — articles that failed the fast path before a crash would silently lose their Playwright retry. The column is durable and queryable.

A separate `article_scrape_queue` table was rejected for being over-engineered at this scale. The status enum on `article` is sufficient and avoids a join in the embedding step when reading `content`.

**Dependency additions.**
- `trafilatura` → `backend/packages/ingest/pyproject.toml`. Pure Python, no Docker change beyond dep-cache invalidation.
- `playwright` → `backend/packages/ingest/pyproject.toml`. Requires: (a) `playwright install chromium` in the `pipeline-build` Dockerfile stage; (b) Chromium system libraries (`libnss3`, `libatk1.0-0`, `libatk-bridge2.0-0`, `libcups2`, `libdrm2`, `libxkbcommon0`, `libxcomposite1`, `libxdamage1`, `libxfixes3`, `libxrandr2`, `libgbm1`, `libasound2`) added via `apt-get` in `pipeline-build`. (c) `--no-sandbox` Chromium flag required when running as non-root inside Docker.
- Both dependencies must be added to `docs/tech-stack.md` before the PR merges.

**Docker impact.** The `pipeline` image budget is ≤ 6GB (docker-sop.md §Image-size budgets). Playwright + Chromium binary adds approximately 400–600 MB. Verify `docker images | grep editor-intelligence` does not exceed budget after the build. Per docker-sop.md §Layer-cache rules, adding `playwright` to `pyproject.toml` invalidates the `deps` stage cache — expected and intentional.

**Embedding step integration.** The `embedding` module reads the text to vectorize. After this change, the priority is: `article.content` if non-null, else `article.first_paragraph`. This fallback is implemented inside `embedding.pipeline` (not in `ingest`), keeping the modules decoupled.

**Implication.**
- A new `ScrapeStatus` enum and two new columns (`content`, `scrape_status`) are added to `core.models.Article`. Migration is Alembic autogenerate.
- A new `ingest/scraper.py` module owns the fast-path logic (httpx + trafilatura + timeout).
- A new `ingest/playwright_worker.py` module owns the Playwright deferred logic.
- `pipeline/runner.py` gains a `scrape_new_articles` call after each ingest+embed tick, and a background `playwright_worker_loop` asyncio task started in `serve`.
- The Playwright worker runs at a fixed poll interval (configurable via `settings`), separate from the 10-minute ingest poll.
- `docs/schema.dbml` must be updated to reflect the two new columns.
- `docs/tech-stack.md` must list `trafilatura` and `playwright` under their respective categories before merging.
- Re-enabling backfill for existing articles requires a new decision entry.

---

## D26. Integrate Google Search Console data into ingest pipeline

**Context.** Script verifikasi (`backend/scripts/gsc_verify.py`) membuktikan service account `user-need@teco-analytics.iam.gserviceaccount.com` bisa menarik data dari GSC property `sc-domain:tempo.co`. Tiga dimensi data tersedia: per page, per query, dan kombinasi page+query. Data ini berguna sebagai scoring input — terutama untuk mendeteksi gap coverage (query volume tinggi tapi tidak ada artikel) dan underperforming articles (posisi > 10 untuk query tertentu).

**Decision.**
1. Tambah tiga tabel raw GSC: `gsc_page`, `gsc_query`, `gsc_page_query`. Masing-masing menyimpan data agregat per period (period_start, period_end) dengan unique constraint sehingga re-fetch idempoten.
2. Module baru `ingest/gsc.py` bertanggung jawab fetch dari GSC API dan upsert ke tiga tabel. Fungsi publik: `run(session, settings)`.
3. GSC fetch dipanggil di awal setiap `cluster_label_score` group — baik dari scheduler harian (06:00 WIB) maupun manual trigger. Data GSC selalu fresh saat cluster+label jalan.
4. `article_gsc_metric` tetap dipertahankan — dipakai scoring untuk underperformance check per artikel internal. Tiga tabel baru adalah raw storage site-wide, bukan pengganti.
5. Dua dep baru ditambahkan ke `ingest/pyproject.toml`: `google-api-python-client>=2.0` dan `google-auth>=2.0`.
6. GSC data tidak pernah keluar ke API (constraint existing tetap berlaku).

**Rationale.** Menempatkan GSC fetch di `ingest` package konsisten dengan pola yang ada — ingest adalah satu-satunya package yang menarik data dari sumber eksternal. Pipeline daemon sudah memiliki daily scheduler; menambahkan GSC fetch sebelum cluster+label tidak membutuhkan scheduler baru. Fetch gagal (network error, credential issue) di-log sebagai WARNING dan tidak menghentikan cluster+label — daemon tetap jalan.

**Implication.**
- Tiga tabel baru membutuhkan Alembic migration.
- `GSC_SITE_URL`, `GSC_CREDENTIALS_PATH`, `GSC_FETCH_DAYS` ditambahkan ke `core/config.py` dan `.env.example`.
- `docs/tech-stack.md` diupdate dengan dua dep baru.
- Credentials file (`teco-analytics-*.json`) disimpan di `backend/` root, di-gitignore, dan di-mount ke container via volume atau secrets saat deploy.

---

## D28. Post-cluster LLM analysis: per-article claim extraction and deduplication

**Context.** After D27, `cluster_insight` surfaces quantitative signals (velocity, competitor count, coverage) but no qualitative picture of what the cluster actually reports. Editors need to know not just "this topic is hot" but "what distinct facts are being reported across these articles" — to identify angles and coverage gaps without reading every article.

**Options considered.**
- New `article_analysis` table (unique on `article_id`) — cross-run cache built in, clean FK, separate ORM model. Cost: new table, new migration, new ORM class, harder to query per-cluster without joining through `article_cluster_member`.
- JSONB column on `cluster_insight` — no new table, everything co-located. Rejected: `cluster_insight` is tied to `article_cluster.id` which is a fresh UUID each run, so no cross-run caching; per-article data semantically belongs with the article-cluster join, not the cluster summary.
- `text[]` columns on `article_cluster_member` — no new table, natural home (already the article-in-cluster join with `relevance_score`), composite PK `(cluster_id, article_id)` covers all write and read paths, existing `ix_article_cluster_member_article_id` index enables cross-run cache lookup.

**Decision.** Add `main_entity text` and `information_claims text[]` to `article_cluster_member`. Change `cluster_insight.summary` from `text` to `text[]` to store deduplicated unique claims.

Pipeline step added after score:
1. For each current cluster, fetch member articles ordered by `published_at DESC`.
2. Per article: query `article_cluster_member WHERE article_id = X AND information_claims IS NOT NULL LIMIT 1` — if hit, copy to new row; if miss, call Gemma `extract_article_claims`, write result to current row.
3. After all articles in cluster: call Gemma `deduplicate_claims` with all `information_claims` — write unique claims list to `cluster_insight.summary`.

`labeling` package is extended (not split) since both cluster labeling and article analysis use the same Gemma singleton. No new package.

**Rationale.** `article_cluster_member` is the correct granularity: each row already represents one article's participation in one cluster run. Adding extraction columns there means the cache lookup is a simple index scan on `article_id`, and the per-cluster read is `WHERE cluster_id = X` with no extra join. `text[]` over `jsonb` because claims are a flat list of strings — no internal structure.

`n_ctx` raised from 2048 to 4096 on the Gemma singleton to accommodate full article content (D25 scrapes full body) and multi-claim deduplication context.

**Implication.**
- `article_cluster_member`: two new nullable columns. One Alembic migration covers all schema changes.
- `cluster_insight.summary`: type changes `text → text[]` in the same migration. Existing NULL rows unaffected.
- `labeling` package: two new functions (`extract_article_claims`, `deduplicate_claims`), `n_ctx` raised to 4096, `MAX_TOKENS` becomes per-call argument.
- Pipeline execution order: cluster → label → score → **analysis** (new step). Analysis calls `labeling` functions; `pipeline/runner.py` gains one new step call.
- API: `cluster_insight.summary` surfaced as `list[str] | None` in cluster detail response. Pydantic schema updated in the same PR.
- FE: `gen:api` must be re-run after API change; `schemas.ts` updated.
- Re-running analysis on a manual trigger re-uses cached `information_claims` from the morning run for unchanged articles — only new articles since the last run incur a Gemma call.

---

## D27. Re-enable scoring with raw signals (supersedes D24's scoring-disabled clause)

> **Status: Supersedes D24's "scoring step disabled" clause only.** D24's other decisions (cron → daemon, ingest+embed merge, removed `/ingest-embed` endpoint, 7-day cluster window) all stand. Mark this at the top of D24 inline.

**Context.** D24 disabled `scoring.pipeline.run` because the composite outputs (velocity blend + novelty + coverage + `recommendation` enum) didn't earn editor trust. PRD §6 had already mandated raw signals: editors trust raw numbers, not opaque composite scores.

**Options considered.**
- (a) Keep scoring off, render only labels + member counts. No ranking; no "trending" surface.
- (b) Re-introduce composite blend with tuned weights. Same trust failure mode.
- (c) Replace composite with raw, named, threshold-derived booleans + one explicit ratio.

**Decision.** Option (c). `cluster_insight` retains `trend_velocity` (redefined as `count_24h / count_7d`), `summary`, `calculated_at`, `cluster_id`, `id`. Adds `competitor_count`, `trend_match_count`, `tempo_covered`, `last_internal_days_ago`, `underperformed`. Drops `novelty_score`, `coverage_score`, `recommendation`, and the `InsightRecommendation` Postgres enum type. Old rows are wiped in the migration.

**Rationale.** Editors read raw numbers; composites hide tradeoffs. Booleans make API filters trivial: `/morning` = "uncovered & high velocity", `/deferred` = "high velocity & uncovered & stale". All thresholds are config-driven (D7's pattern), so tuning doesn't require schema changes. The `aligned_trends` boolean is explicitly *not* a column — FE computes `trend_match_count > 0` as a single source of truth.

**Implication.**
- `scoring.pipeline.run()` rejoins the daemon's cluster → label → score chain.
- `/morning` and `/deferred` switch from no-join / saturated-only to INNER JOIN on `cluster_insight`. The first post-deploy scoring run produces rows; until then, both endpoints return `[]`.
- GSC raw values still never leak to the API; only `underperformed: bool` derived per D7.
- Scoring queries are batched: 3 aggregate SQL statements per `run()`, not N+1 per cluster. Tests guard this.
- Trends ingest's `scrape_status=NULL` bug must be fixed first (PR-1) — see decision body for why.

---

## D29. Decouple analysis pipeline step from cluster-label-score group

**Context.** D28 added `labeling.analysis.run()` as the fourth step inside `_run_cluster_label_score()`, chained under the same `cluster_label_score` lock. The analysis step runs per-article LLM extraction across all clusters (~100+ minutes). This holds the lock for the entire duration, blocking any manual re-trigger of clustering while analysis is in progress. The cluster label (written by `labeling.pipeline.run()` in step 2) is what editors need for the basic cluster view — analysis output (`main_entity`, `information_claims`, `cluster_insight.summary`) feeds only the AI editor feature and is not needed for cluster browsing.

**Options considered.**
- Keep the sequential chain; accept the lock duration as the cost of simplicity.
- Fire analysis as `asyncio.create_task` after releasing the cluster lock (no dedup, no manual trigger).
- Add a separate `"analysis"` pipeline group with its own lock, worker, asyncio queue, and `pg_notify` channel — symmetric with the existing `cluster_label_score` group.

**Decision.** Separate `"analysis"` pipeline group. After `cluster + label + score` completes successfully, `_cluster_worker` enqueues analysis non-blockingly. A new `_analysis_worker` task picks it up, acquires its own `pipeline_group_lock` row keyed `"analysis"`, runs `_run_analysis()`, then releases the lock. A new `pg_notify` channel `pipeline_analysis_requested` and `POST /api/v1/pipeline/analysis` endpoint enable manual trigger. `GET /api/v1/pipeline/status` exposes `analysis: datetime | null` alongside `cluster_label_score`.

**Rationale.** The existing worker/lock/notify pattern is the right abstraction — reusing it keeps both groups symmetric with no new primitives. The lock guards against concurrent auto-enqueue + manual trigger producing duplicate LLM runs. Fire-and-forget without a lock was rejected for that reason. The `run-daily` CLI keeps analysis in its sequential chain — it is an operator debug tool, not a production path, so blocking is acceptable there.

**Implication.**
- `runner.py`: `_run_cluster_label_score()` no longer calls `analysis_run()`. New constants `_GROUP_ANALYSIS`, `_CHANNEL_ANALYSIS`. New `_run_analysis()` and `_analysis_worker()`. `_cluster_worker` gains `analysis_queue` param and auto-enqueues on clean success. `_listen()` gains `analysis_queue` param and handles `_CHANNEL_ANALYSIS`. `run_loop()` adds `analysis_queue` and a sixth task.
- `api/routes/pipeline.py`: New constants `_GROUP_ANALYSIS`, `_CHANNEL_ANALYSIS`. `PipelineStatusResponse` gains `analysis: UtcDateTime | None`. New `POST /api/v1/pipeline/analysis` endpoint. Stale summary on cluster-label-score endpoint corrected.
- Frontend: `PipelineStatusSchema` drops stale `ingest_embed` field (removed in D24, never cleaned up), adds `analysis`. `useTriggerIngestEmbed` hook removed (called deleted endpoint). `useTriggerAnalysis` added. `sources.tsx` drops "Ingest + Embed" button, adds "Analysis" button. `generated.ts` regenerated after backend deploy.

---

## D30. Reuse `pipeline_group_lock.locked_at` as a lease heartbeat (no migration)

**Context.** A stale `pipeline_group_lock` row (left by a SIGKILLed container) was orphaned for 9 days because the daemon had no TTL, no heartbeat, and no startup reaper. The ML-blocking asyncio loop made SIGTERM unobservable → Docker SIGKILL after 10s → `finally: _release_lock()` never executed. Every scheduled and manual trigger silently no-opped with `"lock already held, skipping"`.

**Options considered.**
- Add a new `expires_at` column (Alembic migration required; simple to reason about).
- Use PostgreSQL advisory locks (no table needed; but harder to inspect via `psql` and outside the existing ORM pattern).
- Reuse `locked_at` as a heartbeat timestamp — daemon bumps it every N seconds; rows older than TTL are treated as expired and reaped.

**Decision.** Reuse `locked_at` as the lease heartbeat. No schema migration needed.

**Rationale.** The daemon is a singleton (CLAUDE.md constraint), so concurrent heartbeat writes to the same row cannot race. `locked_at` is already indexed (PK lookup), observable via `psql`, and used by the existing `/pipeline/status` endpoint. Adding a column would require a migration and a deploy window with no behavioral advantage. Advisory locks were rejected because they are session-scoped (connection pool churn drops them silently) and cannot be inspected from the API.

The margin is safe: the longest blocked native call after the `asyncio.to_thread` offload (introduced in the same PR) is one embed batch (~102s) or one UMAP/HDBSCAN call — both ≪ the 300s lease TTL. Heartbeat fires every 30s while the loop is free between `to_thread` calls.

**Implication.**
- `core/config.py`: two new settings: `pipeline_lock_lease_ttl_seconds: int = 300`, `pipeline_lock_heartbeat_seconds: int = 30`.
- `runner.py`: `_acquire_lock` first DELETEs any expired row (separate txn), then attempts INSERT. New `_heartbeat` task bumps `locked_at` every 30s for `_held_groups`. Startup reap in `run_loop` clears both groups' stale rows before spawning tasks. Workers track `_held_groups` for the heartbeat.
- `api/routes/pipeline.py`: `_trigger` reaps expired rows before the 409 check — a dead daemon's stale lock no longer blocks manual recovery.
- All datetime comparisons use naive UTC (`datetime.now(UTC).replace(tzinfo=None)`) to match the stored column type.


---

## D31. Single-call cluster insight; analysis fan-out folded into labeling

**Context.** After D28/D29, the labeling + analysis pipeline required ~1,610 Gemma-2B-Q4 LLM calls per daily run (~7 calls × ~230 clusters for labeling, plus ~5 calls × ~230 clusters × ~1.4 articles avg for analysis). On CPU, each call takes ~55s, giving a total wall-time of ~27h — longer than the 24h scheduling window, so labeling never completed. Additionally, `editorial_angle` was populated on only 3/229 clusters (1.3%), because the old `_INSIGHT_USER` prompt placed `SUDUT:` *after* the variable-length `PIHAK:` list; when `max_tokens=384` was exhausted, the model stopped before reaching `SUDUT:`.

**Options considered.**
- Keep per-article extraction + cluster-level dedup (D28/D29 design). Too slow; ~27h wall-time.
- Batch articles into one call per cluster with existing LABEL+APA_TERJADI+PIHAK+SUDUT fields. Reduces calls but doesn't fix SUDUT truncation without reordering fields.
- Single call per cluster with sub-cluster representative selection (cosine ≥ 0.90 + greedy MMR cap 20) and reordered output fields (SUDUT before variable-length PIHAK+KLAIM). Reduces to ~230 calls and fixes the truncation root cause.

**Decision.** Option (c). One Gemma call per cluster using:
1. Sub-cluster intra-cluster members at cosine ≥ 0.90 (UnionFind, free), pick highest-relevance rep per sub-group, MMR-diversify to 20 reps max.
2. New field order: `LABEL → APA_TERJADI → SUDUT → PIHAK[] → KLAIM[]`. `SUDUT` comes before both variable-length lists so token budget exhaustion eats `KLAIM`, not the angle.
3. `max_tokens=600` (was 384 for insight, 512 for claims).
4. n_ctx=4096 budget guard: trims reps until `prompt_tokens + 600 ≤ 3968`; logs WARNING on trim.
5. Robust parser via regex `(?P<key>LABEL|APA_TERJADI|APA\s+TERJADI|SUDUT|PIHAK|KLAIM)\s*:` (case-insensitive) — tolerates markdown bold, numbered bullets, and `SUDUT :` (space before colon).
6. `analysis.run()` is a no-op stub (`{"analyzed": 0, "skipped": 0}`); the D29 group/lock/channel/endpoint are preserved to avoid API contract churn (full removal deferred to PR5/post-MVP).

**Rationale.** The representative selection reduces input noise: near-duplicate articles (cosine ≥ 0.90) contribute only one voice. MMR diversification ensures coverage. Moving `SUDUT` before `PIHAK[]` is the direct fix for the 1.3% fill rate — it's a prompt-order change, not a parser change. The non-destructive `_upsert_insight` (only overwrite a field when the new value is non-None) fixes fallback clobber: if labeling falls back to `generate_label` (label-only), the existing `what_happened`/`editorial_angle` from a prior run are not wiped.

**Implication.**
- `labeling/pyproject.toml`: add `numpy>=1.26`.
- `labeling/prompts.py`: new `format_cluster_insight_messages(reps)` + `FIRST_PARA_MAX_CHARS=350`.
- `labeling/llm.py`: `_token_len`, `_parse_cluster_insight`, `_cluster_insight_sync` (trim-then-generate under `_llm_lock`), `async generate_cluster_insight`.
- `labeling/pipeline.py`: `_get_representative_articles` (sub-cluster + MMR), `_upsert_insight` gains `summary` param and non-destructive semantics, `run()` calls `generate_cluster_insight` with fallback ladder.
- `labeling/analysis.py`: no-op stub; `_load_cluster_articles`, `_find_cached_claims`, the `UPDATE article` cache-write, and `deduplicate_claims` call are all removed.
- Expected call count: ~1,610 → ~230 (8× reduction). Expected wall-time: ~27h → 60–90 min (CPU).
- `editorial_angle` fill rate: 1.3% → ≥90% (field-order + max_tokens fix, not parser).

---

## D32. Freshness guard on served cluster run

**Context.** After the 9-day daemon outage (D30), the API continued serving a 9-day-stale cluster run with no indication to the frontend. The caller had no way to distinguish live data from severely stale data.

**Options considered.**
- Reject stale runs (return 503 when run age > max_age_hours). Safe but breaks availability: during any daemon outage, the dashboard goes blank.
- Add `is_stale: bool` + `served_at: datetime | None` to each list response (flag, don't reject). Dashboard always serves what it has; consumers can surface a warning banner.
- Per-cluster staleness in `ClusterSummary` (spreads the field across every item). Verbose; the run-level flag is sufficient for the list view.

**Decision.** Option (b): wrap list endpoints in a `ClusterListResponse` envelope `{clusters, served_at, is_stale, max_age_hours}`. `ClusterDetail` also gains `is_stale` (computed from the cluster's own `insight.calculated_at`). Flag, don't reject.

**Rationale.** Outage availability trumps freshness enforcement. The banner UI (deferred to the FE team) needs the metadata attached to the list, not per-item, so a list envelope is the minimal shape. `served_at = MAX(ClusterInsight.calculated_at)` for the served run is computed in one extra DB query per list call — cheap on a local DB. `is_stale = (now - served_at) > max_age_hours` where `max_age_hours = 36` (config `cluster_staleness_max_age_hours`): one missed 06:00 run (24h) is fine; two missed runs (48h) should trigger the banner.

**Implication.**
- `core/config.py`: `cluster_staleness_max_age_hours: int = 36`.
- `api/routes/clusters.py`: `ClusterListResponse` envelope; `_get_served_at(session, run_filter)` helper; `_compute_is_stale(served_at)` helper; `is_stale: bool` on `ClusterDetail`.
- `response_model=` updated for `morning`, `deferred`, `current`, and `{id}` routes (same commit, per API-contract rule).
- Breaking change (pre-1.0, per constraints.md): `morning`, `deferred`, `current` responses change from bare arrays to envelopes. FE consumers updated to access `.clusters`.
- FE banner UI deferred to FE team.

---

## D33. Cluster run retention + ON DELETE CASCADE

**Context.** The API only ever serves the latest scored run (`is_current`), but every daily run appends a fresh generation of `article_cluster` (+members) and `cluster_insight` rows that are never read again and never pruned. After ~18 runs the dev DB held 8,092 clusters / 155k members / 5,185 insights — unbounded growth, larger backups, slower scans. Pruning was impossible anyway: the child FKs (`cluster_insight.cluster_id`, `article_cluster_member.cluster_id`, `article_cluster.run_id`, `article_cluster.parent_cluster_id`) were all `NO ACTION`, so deleting an old run/cluster raised a FK violation. (Note: there were 0 truly-dangling rows — "orphans" earlier meant rows of non-current runs, not broken FKs.)

**Options considered.**
- Leave it. Unbounded growth; eventually an operational problem.
- Periodic prune of old `article_cluster` rows, keeping `cluster_run` shells. Keeps a clean run history but needs CASCADE on the cluster_id FKs anyway and leaves empty runs behind.
- Prune whole `cluster_run` rows with `ON DELETE CASCADE` down the tree. One delete statement; the cascade removes clusters → members + insights.

**Decision.** Option (c). Add `ON DELETE CASCADE` to the four child FKs above (DDL-only migration `e1f3a5c7b9d2`). Add `clustering.pipeline.prune_old_cluster_runs(keep)` — keeps the `cluster_run_retention_count` (=14) most-recent runs **plus** every run still owning `is_current` clusters, then deletes the rest. Called at the end of `cluster_label_score.run()` (after scoring) and exposed as `python -m pipeline.cli prune` for ad-hoc/one-time cleanup. `article_cluster_member.article_id` stays `NO ACTION` (articles are an immutable corpus, never deleted).

**Rationale / safety.** Deleting by `cluster_run` is a single statement; the cascade handles the dependent tree, including the 4 self-referential sub-clusters via `parent_cluster_id` CASCADE. The prune is safe by construction: it builds an explicit keep-set, **aborts if that set is empty**, and only issues `DELETE ... WHERE id IN (<materialized old ids>)` — there is no `NOT IN (<subquery>)` that could escalate to a full-table wipe, and the served run is never eligible for deletion. Retention = 14 ≈ two weeks of daily runs (clustering window is 7 days).

**Migration is DDL-only — it deletes no rows.** The one-time cleanup of accumulated old runs happens through the guarded runtime `prune_old_cluster_runs` on the next daily run (or a manual `prune`), not inside the migration. A destructive data migration against the live DB is the higher-risk path; keeping the migration pure DDL makes `alembic upgrade head` non-destructive and trivially reversible.

**Test-isolation hardening (same change).** `alembic/env.py` prefers `$DATABASE_URL` over the cfg url, which meant a test run with `DATABASE_URL` set would redirect the conftest migration step onto the **dev** DB instead of the test DB. `conftest.py::_run_migrations_on_test_db` now pins `DATABASE_URL` to `TEST_DATABASE_URL` for the duration of the upgrade, so test runs can never migrate the dev DB.

**Implication.**
- `core/models.py`: `ondelete="CASCADE"` on the four FKs (parent FK keeps its explicit name `fk_article_cluster_parent_cluster_id`).
- `core/config.py`: `cluster_run_retention_count: int = 14`.
- `clustering/pipeline.py`: `prune_old_cluster_runs`.
- `pipeline/cluster_label_score.py`: prune after scoring; `pipeline/cli.py`: `prune` step.
- `alembic/versions/e1f3a5c7b9d2_*.py`: FK drop/recreate with CASCADE (down reverts to NO ACTION).
- `conftest.py`: pin test DB during migration. `docs/schema.dbml`: `delete: cascade` annotations.
- New `packages/pipeline/tests/test_prune_retention.py`: cascade, served-run protection, within-retention no-op, empty-DB guard.

---

## D34. Cap labeling to top-N clusters when a run is large

**Context.** Daily runs now produce ~700–814 current clusters. Even after D31 reduced labeling to one Gemma call per cluster (~55s on CPU), labeling *every* cluster is ~12h for 800 — far past the daily window, and wasteful: only a small editorial slice is ever surfaced (`morning` top-10, `deferred`, manual browse). The long tail of tiny, non-trending clusters is labeled at full cost but rarely read.

**Options considered.**
- Label everything (status quo). Doesn't fit the window at current cluster counts.
- Hard global cap with no ordering. Bounds cost but may skip the newsworthy clusters.
- Cap with editorial priority: when current top-level clusters exceed `labeling_max_clusters` (=100), label only the top 100 ordered by trend match (distinct trend signals captured in the last 24h that the cluster's articles hit) desc, then `member_count` desc.

**Decision.** Option (c). `labeling.pipeline._select_cluster_ids_for_labeling` ranks current top-level clusters by `(trend_match_count_24h DESC, member_count DESC)` and slices to `settings.labeling_max_clusters`. The trend-match join mirrors scoring's `_load_trend_match` (same 24h `captured_at` window, distinct `trend_signal_id`). When the count is at or under the cap, every cluster is labeled (order only affects processing sequence). `run()` now returns `{labeled, skipped, capped}`.

**Rationale.** Editorial value concentrates in trending and large clusters; the tail seldom surfaces. The cap bounds the Gemma budget to ≤100 calls (≈≤90 min) regardless of how many clusters a run produces. It is self-correcting: each run re-selects, so a cluster that starts trending on a later day gets labeled then. **Scoring is untouched** — all clusters still receive `cluster_insight` signals (velocity, competitor count, coverage); only the qualitative text (label, what_happened, editorial_angle, summary) is capped. An unlabeled capped cluster serves `label=null`, indistinguishable from a not-yet-labeled cluster, so there is no API/contract change.

**Implication.**
- `core/config.py`: `labeling_max_clusters: int = 100`.
- `labeling/pipeline.py`: `_select_cluster_ids_for_labeling` (replaces `_load_current_clusters`); `run()` iterates capped ids and reports `capped`.
- No schema change, no API change.
- New `packages/pipeline/tests/test_labeling_cap.py`: cap honors trend-then-member priority; stale (>24h) trend signals excluded; full order when under cap.

---

## D35. Demand × performance 2×2 editorial matrix (supersedes D27 scoring signals)

**Context.** After D27 and D34 shipped, two defects made the scoring signals effectively dead:

1. **`trend_match_count ≈ 0` everywhere.** `_load_trend_match` filtered `ts.captured_at >= now − 24h`. The daily cluster build ingests articles from the past 7–30 days; their trending signals are days old, not hours. The 24 h window produced ~5 matching clusters out of 2,000+. Compounding this, the scoring counted `trend_signal` rows (one per 10-minute daemon poll) instead of distinct keywords, inflating the rare non-zero values ~23×.
2. **`article_gsc_metric` permanently empty.** `ingest.gsc` fetched `gsc_page` (~56 k rows) but no code ever wrote `article_gsc_metric`. Every GSC-dependent score (`underperformed`, `tempo_gsc_impressions`, `gsc_demand_gap`) was always the default value.

**Goal.** Give the editorial team one clear question per cluster: *does external demand exist, and is Tempo capturing it?* Two orthogonal axes produce a 2×2 matrix surfaced through `editorial_quadrant`.

**Decision.**

1. **Align all analysis windows to `analysis_window_days = 7`** (cluster build, trend match, GSC). `scoring_trend_window_days` controls the trend window (defaults to `analysis_window_days`). The `.env` override `CLUSTERING_WINDOW_DAYS=30` is removed; D27's mandated value of 7 is now enforced.

2. **Fix trend match semantics.** `_load_trend_match` counts `COUNT(DISTINCT ts.keyword)` not `COUNT(DISTINCT tsa.trend_signal_id)`. `_load_weighted_trend_score` uses `SUM(MAX(interest_score) per keyword)` — peak interest per keyword, not a sum over all poll captures.

3. **Populate `article_gsc_metric` daily.** `ingest.gsc.link_articles()` runs immediately after `gsc.run()` in the cluster worker. It matches `gsc_page.page_url` to internal `article.url` via (a) exact normalized URL match and (b) trailing numeric ID fallback for Tempo slug variants, then upserts aggregated GSC signals into `article_gsc_metric`.

4. **Demand scoring (new `scoring/demand.py`).** Per-cluster `demand_score` is a weighted combination of normalised trend_match_count (40%), weighted_trend_score (30%), and trend_velocity (30%), all min-max normalised within the run. `high_demand = demand_score > 0 AND demand_score ≥ demand_high_percentile rank`. Default `demand_high_percentile = 0.66` (top ~34% of run).

5. **Performance scoring (new `scoring/performance.py`).** `performance_level` per cluster: `none` (no Tempo coverage), `too_early` (covered but no GSC data yet — article too new), `high` (covered + impressions ≥ `performance_high_percentile` rank + not underperformed), `low` (everything else). Default `performance_high_percentile = 0.66`.

6. **`editorial_quadrant` (derived).** `opportunity` (high demand + none/low performance), `winning` (high demand + high performance), `evergreen` (low demand + high performance), `ignore` (low demand + low/no performance), `too_early` (covered but no data yet).

7. **`/morning` ranks opportunity first.** `ORDER BY (editorial_quadrant = 'opportunity') DESC, demand_score DESC, trend_match_count DESC, member_count DESC`. **`/deferred` uses `high_demand = true`** as the filter (replaces `trend_velocity > threshold`).

8. **D35 API governance.** Raw GSC numbers (`gsc_impressions`, `gsc_clicks`, `gsc_ctr`, `gsc_avg_position`) are stored in `cluster_insight` as internal scoring inputs but **never returned via the API** (consistent with D7 / constraints.md §GSC). Derived editorial levels (`demand_score`, `high_demand`, `performance_level`, `editorial_quadrant`) are signals, not raw metrics, and are returned — same category as the existing `underperformed` and `tempo_covered` booleans. Fields `gsc_demand_gap` and `tempo_gsc_impressions` are removed from both the schema and API (they were always zero since `article_gsc_metric` was never populated).

**Schema changes.** `cluster_insight` gains `demand_score FLOAT`, `high_demand BOOLEAN`, `performance_level VARCHAR`, `editorial_quadrant VARCHAR`, `gsc_impressions INTEGER`, `gsc_clicks INTEGER`, `gsc_ctr FLOAT`, `gsc_avg_position FLOAT`; drops `gsc_demand_gap`, `tempo_gsc_impressions` (Alembic: `6e62c85f88ee`).

**Config additions.** `analysis_window_days`, `scoring_trend_window_days`, `demand_high_percentile`, `performance_high_percentile`.

**Implication.**
- D27's "scoring inputs only" rule for GSC is refined: internal aggregate columns stay internal; derived editorial labels are surfaced.
- D34's labeling cap join updated to use 7-day window + distinct keyword count (consistent with D35 trend match).
- `constraints.md §73` updated: see that section for the revised wording.
- `docs/plan/pr1…pr5.md` documents the implementation sequence.

## D36 — Cross-process single-flight lock for ML steps + thread caps + deferred `finished_at`

**Context.** The pipeline (labeling in particular) kept crashing, stalling for hours, or appearing "stuck" even after earlier hardening (D30). Root-cause analysis on 2026-06-03 found three compounding defects:

1. `pipeline_group_lock` was only checked by the daemon's in-process `_held_groups` set. One-shot CLI steps (`pipeline label`, `pipeline cluster`, `pipeline cluster-label-score`) never acquired the DB lock, so a manual run could collide with the daemon or another manual run — two Gemma/sentence-transformers runtimes on CPU in the same thread pool → native crash (no Python traceback).
2. No BLAS/OpenMP/llama thread caps anywhere. A single inference job claimed all 12 host cores; two concurrent jobs caused CPU starvation (throughput collapse showing as "stuck") and native BLAS assertions.
3. `ClusterRun.finished_at` was written by `_persist_clusters()` — *before* merge, split, score, and label. The scheduler's `max(finished_at)` boundary check treated a mid-labeling crash as "done", so the next scheduled retry was silently skipped until the following 06:00.

**Options.** (a) Prevent concurrent runs via DB lock (chosen). (b) Move to a separate queue or external coordinator (ruled out — no message broker). (c) Serialise via file lock (no cross-container guarantee in Docker without a shared bind-mount).

**Decision.**

1. **`pipeline/locks.py` — shared lock primitives.** Extracted `acquire_lock`, `release_lock`, `reap_expired_lock`, `bump_lock`, `is_lock_held` from `runner.py` into a standalone module so both the daemon and CLI steps import the same code. Added `hold_lock(group)` async context-manager with its own background heartbeat — wraps any ML block with acquire/heartbeat/release.

2. **CLI ML steps are single-flight.** `pipeline cluster`, `pipeline label`, `pipeline score`, `pipeline cluster-label-score` all acquire `GROUP_CLUSTER_LABEL_SCORE` before running. If the lock is held (daemon or another manual run is active), the step logs an error and exits with code 1 immediately instead of running concurrently.

3. **Thread caps.** `OMP_NUM_THREADS=4`, `OPENBLAS_NUM_THREADS=4`, `MKL_NUM_THREADS=4`, `NUMEXPR_NUM_THREADS=4`, `TOKENIZERS_PARALLELISM=false` set in the `pipeline` and `pipeline-dev` Dockerfile stages. `llm.py` passes `n_threads=4` to llama_cpp. On a 12-core host this gives each inference job predictable headroom without saturating the machine.

4. **`ClusterRun.finished_at` deferred to pipeline end.** `clustering/pipeline.py:_persist_clusters` no longer sets `finished_at`. `cluster_label_score.run()` sets it via `UPDATE` after score → label → prune all succeed. Consequence: the API's `_resolve_cluster_filter` (`finished_at IS NOT NULL`) only serves fully-processed runs; a crash mid-label leaves `finished_at=NULL` so the scheduler fires again on the next boundary.

**Rationale.** The three defects are independent but each one caused recurring "pipeline stuck/failed" incidents. Fix 1 prevents the concurrent-crash mode that was the most common recent symptom. Fix 2 prevents CPU starvation on the GPU-less host (all inference on CPU via BLAS). Fix 3 closes the scheduler-blind-spot that turned every mid-labeling crash into a silent 24-hour gap.

**Implication.**
- `runner.py` re-exports `_acquire_lock`/`_release_lock` from `locks.py` for backward compat with `test_lock_lease.py`.
- Existing `ClusterRun` rows with `finished_at=NULL` (runs that started before this fix) will never get `finished_at` set — they will be invisible to the API's cluster filter and to `prune_old_cluster_runs`'s recency sort (it falls back to `started_at`). No migration needed; normal behaviour.
- The `memswap_limit: 7g` on pipeline-daemon (equal to `mem_limit`) disables swap for the container. This is intentional — an OOM-kill is recoverable (restart + reap stale lock); swap thrashing at 12 GB/s is not.

---

## D37. Embed the Editorial AI Analyst as a separate, API-backed package

**Context.** A standalone "Editorial AI Analyst" app (OpenAI-backed FastAPI + Next.js)
must merge into content-intelligence as one app, without entangling its existing
local-ML pipeline.

**Options considered.**
- Weave analyze/recommendation into existing modules + the pipeline daemon
- New self-contained `analyst` package, API-backed, separate from the daemon
- Keep two apps behind a reverse proxy

**Decision.** New self-contained `analyst` package. Interactive analyze/recommendation
are served via an OpenAI-compatible client (local = local-server base URL, API = hosted).
No in-process model, no daemon involvement. Frontend ported into the Vite app as a new
`@ei-fe/*` feature. LangChain/BigQuery/Lambda/slowapi dropped.

**Rationale.** Preserves "`api` never imports ML", keeps the daemon a singleton owning
only the clustering pipeline, and reduces the local/API switch to a base-URL swap.

**Implication.** The analyst has its own config block and no DB tables initially.
Unifying `labeling` onto the same client, persistence, and live BigQuery are future work.

---

## D38. Expose aggregated per-cluster GSC clicks as `views` on the bento (scoped reversal of D35)

The cluster bento card surfaces editorial pull-through with a `views` tile. The
only traffic signal in the system is GSC, which D35 keeps internal. We reverse
D35 **narrowly**: `cluster_insight.gsc_clicks` (already de-duplicated to one GSC
period per article during scoring) is returned as an aggregated per-cluster
`views` integer on `GET /clusters/bento` only. Impressions, CTR, and average
position remain internal scoring inputs and are still asserted absent from every
response by `test_clusters_no_gsc_leak.py`. No new column, no migration — the
existing aggregate is un-hidden under a non-raw field name.
