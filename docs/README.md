# Editor Intelligence — Documentation

Internal dashboard for Tempo's editorial team. Ingests competitor RSS + Tempo sitemap + Google Trends → clusters by topic → surfaces topics worth writing.

## Read these four before writing code

Everything else in `docs/` is reference material — open it on demand via the router below.

1. `prd.md` — product context, personas, what is explicitly out of scope
2. `architecture.md` — modules, data flow, dependency graph
3. `constraints.md` — what NOT to build (backend + frontend)
4. `schema.dbml` — database tables and relationships

## Task → file router

| What you're doing | Open |
|---|---|
| Adding or changing an HTTP endpoint | `conventions.md` §API endpoints — the contract is FastAPI's `/openapi.json` |
| Touching the frontend | `frontend.md` |
| Frontend component placement (where does X go? when to promote?) | `architecture.md` §Frontend (shape) + `frontend.md` §Promotion rule + §Styling system priority |
| Adding a top-level dependency | `tech-stack.md` (update it in the same PR) |
| Docker, compose, or image change | `docker-sop.md` |
| Logging — fields, levels, request IDs | `logging-sop.md` |
| Running, debugging, or recovering the stack | `operations-sop.md` |
| Changing the pipeline schedule, scoring toggle, or cluster window | `decisions.md` D24 + `operations-sop.md` §Pipeline scheduler |
| Hardening an existing feature | `hardening-sop.md` |
| Reviewing a PR | `review-sop.md` |
| "Why was X chosen?" | `decisions.md` |
| "Is X allowed?" | `constraints.md` |

## Sources of truth

- **Hard constraints**: `constraints.md`. If another doc contradicts it, fix the other doc.
- **Database schema**: `backend/packages/core/src/core/models.py` (SQLAlchemy ORM). `schema.dbml` is a documented mirror.
- **Deferred features**: PRD §6. Don't reintroduce without explicit user approval.

## When in doubt

Ask the user before assuming. Do not invent features, alternative architectures, or scope expansions.
