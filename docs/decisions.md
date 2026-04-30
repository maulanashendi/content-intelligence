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

**Implication.** Multi-stage Dockerfile contains both `api` and `pipeline` targets. docker-compose.yml is the dev composition; production overrides go in `docker-compose.prod.yml` if needed.

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

**Context.** Docker-related files can live at repo root or in a `docker/` subfolder.

**Options considered.**
- `docker/Dockerfile` and `docker/docker-compose.yml` (subfolder)
- `Dockerfile` and `docker-compose.yml` at repo root

**Decision.** Root-level.

**Rationale.** `docker compose up` works from the project root without `-f` flags or path tricks. Build context is intuitive (`context: .`). Standard Python and Node convention. CI tooling (GitHub Actions, etc.) defaults to root paths. Subfolder organization adds friction for every developer for marginal aesthetic gain.

**Implication.** Multi-stage Dockerfile contains both `api` and `pipeline` targets. docker-compose.yml is the dev composition; production overrides go in `docker-compose.prod.yml` if needed.
