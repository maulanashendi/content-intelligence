# Editor Intelligence — Documentation

This directory is the handover package for any contributor — human or AI agent — joining work on Editor Intelligence. Read the files below in order before writing code. Skipping ahead leads to wrong assumptions and rework.

## What this project is

An internal dashboard for Tempo's editorial team. Each morning it ingests articles from competitor RSS feeds, Tempo's internal sitemap, and Google Trends; clusters them by topic; and surfaces topics worth writing that the team has not yet covered.

The product target is one user persona (Maulana, content editor for the economy desk) making 2-3 daily topic decisions in under 15 minutes, replacing a 1-hour manual scan.

## Repository layout

```
editor-intelligence/
├── docs/           # this folder — product spec, architecture, decisions
├── backend/        # all backend code (Python uv workspace, Dockerfile, alembic, ...)
├── frontend/       # production frontend (Bun workspace, Vite SPA — see frontend.md)
└── template-fe/    # legacy visual prototype, will be deleted after migration (decisions.md D18)
```

Backend commands run from `backend/`; frontend commands run from `frontend/`. See `conventions.md` and `frontend.md` for details.

## Required reading order

Read these files top to bottom. Each file assumes you have read everything above it.

| # | File | What you will know after reading |
|---|------|----------------------------------|
| 1 | `README.md` (this file) | The map of this documentation |
| 2 | `prd.md` | Product context, personas, happy path, what is explicitly out of scope |
| 3 | `architecture.md` | System structure, modules, data flow, dependency graph |
| 4 | `schema.dbml` | Database tables, columns, relationships |
| 5 | `api_contract.md` | HTTP contract — live and proposed endpoints, error envelope, open conflicts |
| 6 | `tech-stack.md` | Concrete libraries and versions, what was rejected and why |
| 7 | `conventions.md` | Code layout rules, import boundaries, dev workflow |
| 8 | `constraints.md` | What NOT to build, deferred features, schema invariants (backend + frontend) |
| 9 | `frontend.md` | Frontend architecture: packages, dependencies, routing, data layer, conventions |
| 10 | `decisions.md` | Rationale behind every non-obvious choice (backend: D1–D11, frontend: D12–D18) |

Estimated reading time end-to-end: 85-115 minutes.

## Mental model you should hold after reading

After completing the reading list above, you should be able to answer:

- Which user makes which decision, when, and what data backs it.
- Which module owns which piece of logic, and how it depends on other modules.
- Which database table answers which product question.
- Which library was chosen over which alternative, and why.
- Which features were deliberately deferred and must not be re-introduced without explicit user approval.
- Which architectural patterns are forbidden (microservices, message queues, etc.).

If any of these is unclear, re-read the relevant file before contributing.

## When in doubt

If a question is not answered in these nine files, ask the user before assuming. Do not invent features, alternative architectures, or scope expansions on your own. The PRD's `Section 6 — What we will NOT build in MVP` is the authoritative deferral list.

## Quick reference

- Product spec: `prd.md`
- Database schema source of truth: `schema.dbml`
- For "is X allowed?" questions, check `constraints.md` first
- For "why was Y chosen?" questions, check `decisions.md`
