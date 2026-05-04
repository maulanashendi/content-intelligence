# Hardening SOP

> **Decay markers.** Any "current state / known issue / hardening task" note in any SOP must carry an `as of YYYY-MM` stamp. When the underlying issue is fixed, remove the marker in the same PR. Stale markers without dates are treated as bugs.

This is the standard procedure for "harden feature X" tasks in Editor Intelligence. Written for AI agents and humans. The MVP is shipped; this SOP is the rubric for making each existing feature production-grade without changing its scope.

The SOP is opinionated on purpose. "Hardening" is the point in a project where scope creep masquerades as quality. The checklist exists to keep the work contained.

## When this applies

- Any task framed as "harden X", "make X production-ready", "add observability to X", "make X idempotent", "add retries to X", or "improve error handling for X".
- Any post-MVP change that is not a new user-visible feature.

If the task is framed as "add a new X", "support a new source type", "improve cluster quality", or anything else that changes user-visible behavior, this SOP does not apply — that work goes through the regular PR flow with a `decisions.md` entry if needed.

## Definition

**Hardening is making an existing feature production-grade without changing what it does.**

What hardening *is*:
- Adding timeouts and retries on external calls.
- Making operations idempotent so re-runs are safe.
- Adding observability (structured logs, request IDs).
- Documenting and handling each failure mode.
- Imposing resource bounds (memory, batch sizes, queue depths).
- Containerization (running as `USER app`, healthchecks, image budget).
- Smoke tests for the happy path and one failure path.

What hardening is *NOT*:
- Adding new endpoints, new data sources, or new ML steps.
- Refactoring across module boundaries to "clean up".
- Performance tuning beyond resource bounds (separate investigation).
- Changing the schema (use Alembic + decisions entry).
- Replacing a dependency (use a decisions entry).
- Adding features deferred in `docs/prd.md` §6.

If the work needs any of the "is NOT" items, stop and re-scope before proceeding.

## The seven-item checklist

Walk every item. For each, mark ✅ done, ❌ missing, or N/A with a one-line reason. The PR body lists the table.

### 1. Boundaries

Every external call has a timeout, a retry policy, and a structured error log.

| Call type    | Timeout     | Retry                                                          | Log on failure                       |
| ------------ | ----------- | -------------------------------------------------------------- | ------------------------------------ |
| Outbound HTTP| 30 s default (`INGEST_TIMEOUT_SECONDS`) | Retry once on 5xx + connect errors; never on 4xx | `logger.exception("...")` with URL |
| LLM inference| Per-call (model-dependent)              | No retry — re-run the labeling step instead       | `logger.exception("...")` with cluster_id |
| DB query     | None at app level (use connection pool timeout) | None — DB is local                            | `logger.exception("...")` with operation |
| File / model load | None — startup-time                | None                                                       | Fail-fast at startup                |

Internal calls (one Python module → another) do NOT get timeouts or retries. They are typed and trusted.

### 2. Idempotency

Re-running the same operation produces the same result. Document the idempotency key in code or in a one-line comment.

| Feature       | Idempotency key                              | Mechanism                                |
| ------------- | -------------------------------------------- | ---------------------------------------- |
| Article ingest| `article.url`                                | `ON CONFLICT (url) DO NOTHING`           |
| Embedding     | `article_embedding.article_id` (unique)      | INSERT ... ON CONFLICT DO NOTHING        |
| Clustering    | `cluster_run.id` per run; `is_current` flip | Atomic transaction                       |
| Labeling      | `article_cluster.id`                         | UPDATE — running twice produces same label at temperature=0 (D5) |
| Scoring       | `cluster_insight.cluster_run_id`             | UPSERT                                    |
| Source CRUD   | `content_source.id`                          | Standard PK                               |

If the feature you are hardening is not in this table and re-running is not safe, **add idempotency before anything else** on the checklist.

### 3. Observability

Per `docs/logging-sop.md`:

- INFO log at start with relevant context (counts, source_id, etc.).
- INFO log at end with `elapsed_s` and result counts.
- ERROR log on failure with `logger.exception(...)` and the unit-of-work identifier.
- `request_id` propagated through context if the work was triggered by an API request.

Verify by running the feature locally and `jq`-grepping its logs.

### 4. Failure modes

List every failure mode in the PR body. For each, decide one of:

- **Fail fast** — raise to the caller, abort the unit of work.
- **Skip + log** — log a WARNING with the reason, continue with the next item.
- **Retry** — bounded retry per the rules in §1.

If the feature introduces a new failure mode (a new external dependency, a new state machine, etc.), document it in code with a one-line comment and update this SOP if the failure-mode table needs a new pattern.

### 5. Resource bounds

Every loop, queue, and cache has an explicit bound. Cite the bound in code.

| Resource              | Current bound                                     | Where                                        |
| --------------------- | ------------------------------------------------- | -------------------------------------------- |
| Ingest immediate queue| 1024 entries (`IMMEDIATE_QUEUE_MAX`)              | `packages/ingest/src/ingest/runner.py`       |
| Pipeline daemon RAM   | 3 GB (compose `deploy.resources.limits.memory`)   | `docker-compose.prod.yml`                    |
| Embedding batch size  | 32–64                                             | embedding pipeline                           |
| Clustering window     | 30 days (`CLUSTERING_WINDOW_DAYS`)                | settings                                     |
| Source block duration | 3600 s (`BLOCK_DURATION`)                         | ingest runner                                |
| Poll interval         | 600 s (`POLL_INTERVAL`)                           | ingest runner                                |

If the feature has an unbounded loop, queue, or cache, **add a bound before merging**.

### 6. Docker

Per `docs/docker-sop.md`:

- Runs in the existing build/runtime/dev triple, or adds a new one if it is a new long-running process.
- Runtime stage runs as `USER app` (non-root).
- Healthcheck defined in compose.
- Image stays under the budget table in §"Image-size budgets".

### 7. Tests

A hardening change is not done until both pass:

- **Happy-path smoke** — one minimal end-to-end exercise per `docs/review-sop.md` §"Phase 4 — Smoke test". Document the command in the PR body.
- **One failure-path test** — the failure mode you most care about (timeout, malformed input, transient DB error). Unit test or scripted exercise; pick one.

Edge-case test coverage is not the goal. The goal is to prove the failure handling actually fires.

## PR template for hardening work

Title: `harden(<module>): <feature>` — e.g., `harden(ingest): rss fetch retries and timeouts`.

Body:

```markdown
## Scope

What feature is being hardened? Cite file paths.

## Hardening checklist

| # | Item                | Status | Notes                                              |
|---|---------------------|--------|----------------------------------------------------|
| 1 | Boundaries          | ✅ / ❌ / N/A | (one line)                                  |
| 2 | Idempotency         | ✅ / ❌ / N/A | (one line)                                  |
| 3 | Observability       | ✅ / ❌ / N/A | (one line)                                  |
| 4 | Failure modes       | ✅ / ❌ / N/A | (list them, one line each)                  |
| 5 | Resource bounds     | ✅ / ❌ / N/A | (one line)                                  |
| 6 | Docker              | ✅ / ❌ / N/A | (one line)                                  |
| 7 | Tests               | ✅ / ❌ / N/A | (smoke command + failure-path test name)    |

## Smoke command

(The exact command run, and what it produced.)

## Out of scope (deferred)

(Anything noticed during hardening that is a separate task. Do not silently expand scope.)
```

The PR review (per `docs/review-sop.md`) will reject hardening PRs whose checklist is missing or whose ❌ items are not justified.

## What this SOP is not

- A redesign manual. If hardening uncovers a design problem, file a `decisions.md` entry separately — do not bundle a redesign into the hardening PR.
- A refactor charter. Three similar lines is not a pattern (`docs/constraints.md`).
- A performance tuning guide. Performance work is a dedicated investigation, separate from hardening.

## Cross-references

- `docs/docker-sop.md` — image hardening rules referenced in checklist item 6.
- `docs/logging-sop.md` — logging contract referenced in item 3.
- `docs/operations-sop.md` — runtime supervision context for items 4 and 5.
- `docs/review-sop.md` — review process and smoke-test patterns referenced in item 7.
- `docs/constraints.md` — what hardening must not introduce; deferred features stay deferred.
- `docs/decisions.md` — record any non-obvious choice made during hardening as a new decision entry.

## Specific rules for AI agents

- **Walk the checklist explicitly.** Do not summarize "I hardened the daemon"; produce the seven-row table with status and notes.
- **Never silently expand scope.** If the user asked you to harden ingest fetching, do not also rewrite the embedding loop. List it under "Out of scope (deferred)" instead.
- **Never approve your own hardening PR.** Review uses `docs/review-sop.md`.
- **Cite the SOPs by path and section** in the PR body and in commit messages.

## Specific rules for human reviewers

- **Reject PRs without the checklist table.** Bouncing them back is cheaper than reviewing scope creep.
- **Verify the failure-path test actually fires the failure.** Authors sometimes write a test that covers the happy path under a "failure" name.
- **Do not approve "harden X" PRs that change user-visible behavior.** That is feature work in disguise; redo as a regular PR with a decisions entry.
