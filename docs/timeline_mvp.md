# MVP Timeline

Concrete execution plan for the Editor Intelligence MVP. Status checkboxes track progress; each AI agent updates the relevant row when starting (`[~]`) and completing (`[x]`) a task.

For architecture, conventions, constraints, and decisions, see the other docs in this folder. This file is the **what to do next, in what order, and when it is done** plan — not the rationale.

## Status legend

- `[ ]` not started
- `[~]` in progress
- `[x]` done

## Baseline (current state)

| Component | Status |
|-----------|--------|
| Backend scaffolding (`backend/`) | [x] |
| Frontend scaffolding (`frontend/`) | [x] |
| Documentation (`docs/`) | [x] |
| Module Python / TS files | placeholder comments only |
| Postgres + Docker dev env | not yet validated |
| Alembic baseline migration | not yet generated |

## Critical path

```
P0 → P1 (cores) → P2 (8-way parallel fan-out) → P3 (composition) → P4 (app shell) → P5 (integration) → P6 (E2E)
```

Modules in the same phase that can run in parallel share the same row group. Inter-phase work is sequential.

---

## P0 — Environment validation

**Duration:** 0.5-1 day · **Parallel:** ✅

| ID | Task | Done when |
|----|------|-----------|
| `[ ]` P0-BE | `cd backend && cp .env.example .env && uv sync && docker compose up -d postgres` | `uv sync` returns 0; postgres `pg_isready` succeeds |
| `[ ]` P0-FE | `cd frontend && bun install && bun --filter @ei-fe/app run dev` | Vite dev server boots without errors |

---

## P1 — Foundation modules

**Duration:** 2-3 days · **Parallel:** ✅ · **BLOCKS:** P2

| ID | Module | Deliverable | Done when |
|----|--------|-------------|-----------|
| `[ ]` A1 | `backend/core` | SQLAlchemy 2.0 models mirroring all 10 tables in `schema.dbml`. Async engine + session factory. Pydantic `Settings`. Alembic baseline migration. | `alembic upgrade head` creates every table; `from core.models import Article` succeeds |
| `[ ]` A2 | `frontend/@ei-fe/core` | Env validator (`VITE_API_BASE_URL`), design tokens, domain types, BI date / number formatters, `ApiError` class | `bun --filter @ei-fe/core test` passes; types re-exported from `src/index.ts` |

---

## P2 — Independent modules (fan-out)

**Duration:** 5-7 days · **Parallel:** ✅ — 8 modules dispatchable simultaneously

Each module depends only on its respective `core` from P1. FE modules (F1, F2) use MSW mocks and JSON fixtures, so they do NOT block on BE completion.

### Backend (B1-B6)

| ID | Module | Key files | Done when |
|----|--------|-----------|-----------|
| `[ ]` B1 | `backend/ingest` | `rss.py`, `sitemap.py`, `trends.py`, `pipeline.py`, `cli.py` | `python -m ingest.cli run` populates `article` from ≥2 mock RSS sources idempotently; trend rows persisted with article links |
| `[ ]` B2 | `backend/embedding` | `embedder.py` (singleton), `pipeline.py`, `cli.py` | 50 sample articles produce 50 `article_embedding` rows of shape `(768,)` with `model_name` populated |
| `[ ]` B3 | `backend/clustering` | `reducer.py` (UMAP), `clusterer.py` (HDBSCAN), `pipeline.py`, `cli.py` | Run on fixture vectors produces ≥1 cluster with `is_current=true`; prior-run rows flipped to `false` |
| `[ ]` B4 | `backend/labeling` | `llm.py` (singleton, 4-bit Gemma 2B), `prompts.py`, `pipeline.py`, `cli.py` | **Prerequisite:** 1-day quality spike on 5 sample clusters. Then: 5 fixture clusters get coherent BI labels of 5-7 words |
| `[ ]` B5 | `backend/scoring` | `velocity.py`, `novelty.py`, `coverage.py`, `pipeline.py`, `cli.py` | Each fixture cluster produces 1 `cluster_insight` row with valid `recommendation` enum; GSC read only by `coverage.py` |
| `[ ]` B6 | `backend/api` | `main.py`, `deps.py`, `routes/clusters.py`, `routes/articles.py`, `routes/sources.py`, `routes/health.py` | All endpoints serve fixture data; `/openapi.json` accessible; **no GSC field appears in any response** |

### Frontend (F1-F2)

| ID | Module | Key files | Done when |
|----|--------|-----------|-----------|
| `[ ]` F1 | `frontend/@ei-fe/api` | `client.ts` (fetch wrapper), `schemas.ts` (Zod), `queries.ts` (keys + hooks), MSW handlers + fixtures | Hooks (`useMorningClusters`, `useClusterDetail`, `useArticles`, `useSources`, `useCreateSource`, `useToggleSource`, `useDeleteSource`) return mocked data; Zod schemas validate fixtures |
| `[ ]` F2 | `frontend/@ei-fe/ui` | Tailwind preset, vendored shadcn primitives (`Button`, `Table`, `Skeleton`, `Tooltip`, `Sheet`, `Dialog`), layout (`Sidebar`, `StatusBar`, `PageHead`), state components (`ErrorState`, `EmptyState`), Lucide icon registry | Each component renders standalone in test; visible via dev server with valid token values |

**Dispatch:** orchestrator fans out 8 sub-agents, one per module. Each sub-agent reads `docs/architecture.md`, `docs/conventions.md`, `docs/constraints.md` before starting.

---

## P3 — Composition layers

**Duration:** 3-5 days · **Parallel:** ✅ BE and FE composition independent

| ID | Module | Depends on | Done when |
|----|--------|------------|-----------|
| `[ ]` C1 | `backend/pipeline` (orchestrator CLI) | A1, B1-B5 | `python -m pipeline.cli run-daily` against empty DB runs all 5 steps sequentially with structured logs; exits 0 |
| `[ ]` C2 | `frontend/@ei-fe/features` | A2, F1, F2 | Feature views (`morning`, `cluster-detail`, `article`) each cover happy path + error + empty state under MSW; **no cross-feature imports** |

---

## P4 — Application shell

**Duration:** 1-2 days

| ID | Module | Depends on | Done when |
|----|--------|------------|-----------|
| `[ ]` D1 | `frontend/@ei-fe/app` | C2 | Vite SPA boots all routes locally with MSW; `bun run build` produces `dist/`; deep links survive hard refresh |

---

## P5 — Integration

**Duration:** 3-4 days · **Sequential**

| ID | Task | Depends on | Done when |
|----|------|------------|-----------|
| `[ ]` I1 | Backend pipeline run on real data | C1, B6 | Live RSS ingest → clusters scored → `/api/v1/clusters/morning` returns ≥1 real cluster with valid label |
| `[ ]` I2 | Generate FE OpenAPI types | I1, F1 | `bun run gen:api` writes `packages/api/src/generated.ts`; committed; type errors resolved |
| `[ ]` I3 | Replace MSW with live backend | I2, D1 | `VITE_API_BASE_URL` set to dev BE; all routes render live data in browser |
| `[ ]` I4 | Schema drift validation | I3 | Zero Zod runtime errors on happy path; fixtures in `@ei-fe/api/tests/mocks/` updated to match real responses |

---

## P6 — End-to-end test

**Duration:** 2-3 days

| ID | Task | Done when |
|----|------|-----------|
| `[ ]` E1 | Backend daily pipeline E2E | Fresh DB, full pipeline completes <30 min; ≥1 trending cluster surfaced; no GSC field appears in any API response |
| `[ ]` E2 | Frontend happy path | Manual or scripted: `/morning` → click cluster → `/clusters/:id` → navigate `/article` → `/sources`. All routes render correctly against live BE. |
| `[ ]` E3 | Edge cases | EmptyState (0 clusters), ErrorState (API down), Skeleton (slow load), 404 cluster id, malformed response (Zod catches) |
| `[ ]` E4 | Cleanup per `decisions.md` D18 | `template-fe/` deleted; `docs/README.md` references only `frontend/` |

---

## MVP Definition of Done

All boxes checked above, **plus**:

- [ ] Daily pipeline runs end-to-end in <30 minutes on target VPS specs
- [ ] All 4 API endpoints return <500 ms for happy-path queries
- [ ] FE bundle <500 KB gzipped (excluding fonts)
- [ ] Zero `console.error` in browser on happy path
- [ ] No `try / except` swallowing errors in BE pipeline
- [ ] Constraints from `docs/constraints.md` upheld
- [ ] PRD §6 deferred features have NOT been built

---

## Effort & dispatch summary

| Profile | Total |
|---------|-------|
| Solo agent (sequential) | 17-25 days |
| 2 parallel agents (BE + FE split) | 12-16 days |
| Multi-agent fan-out at P2 | **9-12 days** ← recommended |

**Recommended dispatch:** orchestrator coordinates phase transitions; sub-agents execute modules in parallel during P2.

---

## Risks (timeline-specific)

For architecture-level risks see `docs/decisions.md`. This list is operational only.

| Risk | Phase | Mitigation |
|------|-------|------------|
| BI label quality from Gemma 2B | B4 | 1-day quality spike on 5 sample clusters before committing pipeline integration |
| OpenAPI schema drift between BE and FE | F1 → I2 | F1 develops against MSW; `gen:api` + Zod runtime validation catch drift in both directions |
| HDBSCAN cold start (too few articles in first runs) | B3 → I1 | Start `min_cluster_size=3`; tune after 1-2 days of real ingest |
| Single-VPS RAM ceiling during ML steps | I1 | Verify ≥8 GB RAM on target VPS before I1 |
| Cross-feature accidental imports in FE | F2 → C2 | Strict `tsconfig.base.json` paths + ESLint rule blocking internal package imports |

---

## How to update this file

When you start a task, change `[ ]` → `[~]`. When done, change `[~]` → `[x]`. Add a single dated note line under the row only when there is meaningful context (e.g. "B4: spike confirmed Gemma 2B BI quality acceptable, 2026-04-30"). Do not edit acceptance criteria — if they need to change, raise it in conversation first.
