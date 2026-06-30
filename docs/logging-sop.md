# Logging SOP

This is the standard procedure for logging in Editor Intelligence. Every service — `api`, the `pipeline-daemon` (`pipeline.cli serve`), the manual `pipeline` CLI steps (`run-daily`, `cluster`, …), and any future entry point — follows it. Written for AI agents and humans.

The SOP is opinionated on purpose. JSON logs to stdout are the *only* observability surface this codebase produces; per `docs/constraints.md`, monitoring/alerting/dashboards are owned externally. If a log is missing, wrong, or unstructured, the operator sees nothing.

## When this applies

- Any new code that runs inside `api`, `ingest`, `pipeline`, or any batch module.
- Any new CLI entry point or daemon.
- Any change that touches `core/logging.py`, `api/main.py`, or per-module `cli.py` files.
- Any change that introduces an external call (HTTP, DB, LLM, file IO).

## Single source of configuration

`backend/packages/core/src/core/logging.py` exposes `configure_logging(level, file_path=None, max_bytes=..., backup_count=...)`. It is the only sanctioned way to configure logging.

- It installs a `JsonFormatter` (`pythonjsonlogger.json.JsonFormatter`) on a stdout handler.
- It optionally adds a `RotatingFileHandler` when `file_path` is provided.
- It clears existing root handlers, then sets the root logger's level.

**Rule:** every CLI entry point calls `configure_logging(settings.log_level)` exactly once, before any business logic runs. The pipeline CLI also passes `file_path=settings.log_dir / "pipeline.log"`. Modules retrieve loggers via `logger = logging.getLogger(__name__)` — never `logging.basicConfig`, never `print()`.

### Known drift to fix (as of 2026-05)

`packages/api/src/api/main.py` defines its own `_configure_logging()` (uses the legacy `pythonjsonlogger.jsonlogger` import and a different field order). It must be replaced with `configure_logging(settings.log_level)` from `core.logging` so the API matches the rest of the codebase. *This is a hardening task; track it separately. Until it's fixed, the API's log shape can drift from other services.*

## Format

JSON to stdout. The formatter template is:

```
%(asctime)s %(levelname)s %(name)s %(message)s
```

Every record includes `asctime`, `levelname`, `name` (logger module path), and `message`. Additional fields come from `logger.<level>(msg, extra={...})`.

Do not change the formatter template without updating this SOP and any downstream log parser. Field order and field names are part of the contract.

## Levels

| Level   | When to use                                                                  | Examples                                                       |
| ------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------- |
| DEBUG   | Developer-only diagnostics. Off by default in prod (LOG_LEVEL=INFO).         | Per-row processing, raw response bodies, prompt text           |
| INFO    | Normal progress that an operator wants to see.                               | "pipeline started", "step finished", "X articles ingested"    |
| WARNING | Recoverable degradation. The unit of work continued.                         | "skipping blocked source", "queue full, dropping payload"      |
| ERROR   | Unrecoverable in this unit of work. Logged before raising or before exiting. | "fetch failed", "embedding insert failed"                      |

Rules:
- One INFO per pipeline step start/end. One INFO per ingest cycle. One INFO per API request (via middleware — see below).
- Never use `print()`. CI should grep for `print(` in `packages/*/src/` and fail.
- Never log `exc_info=True` on WARNING (it's noise). Use `logger.exception(...)` for ERROR with traceback, or `logger.warning(..., exc_info=True)` only when the traceback genuinely informs operator action.

## Structured fields contract

When a log call carries structured data, use `extra={...}`. Reuse these field names — do not invent variants:

| Field             | Type    | Used in                          | Meaning                                            |
| ----------------- | ------- | -------------------------------- | -------------------------------------------------- |
| `step`            | str     | pipeline                         | One of `ingest`, `embed`, `cluster`, `label`, `score` |
| `elapsed_s`       | float   | pipeline, daemon loops           | Wall-clock seconds, rounded to 2 decimals           |
| `total_elapsed_s` | float   | pipeline                         | End-to-end pipeline duration                        |
| `count`           | int     | batch loops                      | Items processed                                     |
| `counts`          | dict    | step results                     | Per-substep counts (e.g., `{"rss": 23, "trends": 4}`) |
| `source_id`       | UUID    | ingest                           | `content_source.id`                                 |
| `source_name`     | str     | ingest                           | `content_source.name`                               |
| `cluster_id`      | UUID    | clustering, labeling, scoring    | `article_cluster.id`                                |
| `article_id`      | UUID    | ingest, embedding                | `article.id`                                        |
| `request_id`      | str     | api, daemons (when triggered by API) | UUID4 generated per HTTP request, propagated downstream |
| `path`            | str     | api middleware                   | Request path (no query string)                      |
| `method`          | str     | api middleware                   | HTTP method                                         |
| `status`          | int     | api middleware                   | HTTP response code                                  |
| `latency_ms`      | int     | api middleware                   | Request handler latency                             |
| `channel`         | str     | daemons                          | `pg_notify` channel name                            |

If a new field is genuinely needed, add it to this table in the same PR — drift here is the most common SOP failure mode.

### Existing patterns to mirror

- `pipeline.cli._run_daily` (`packages/pipeline/src/pipeline/cli.py`): `logger.info("step finished", extra={"step": step, "elapsed_s": ...})`. This is the canonical example.
- `ingest.runner.run_loop` (`packages/ingest/src/ingest/runner.py`): currently uses `%s` interpolation in the message (`"source=%s ingested %d articles"`). Acceptable but inconsistent — new code should prefer `extra={...}` so structured fields are queryable in JSON.

## API logging (target state, as of 2026-05)

The API currently has no per-request logging. Add a FastAPI middleware at `packages/api/src/api/middleware/logging.py` that:

1. Reads `X-Request-ID` from the incoming request, or generates a UUID4 if absent.
2. Stores it in a `contextvars.ContextVar[str]` named `request_id_var`.
3. Attaches a logging filter that injects `request_id` into every record produced inside the request scope.
4. After the handler returns, logs one INFO line with `method`, `path`, `status`, `latency_ms`, `request_id`.
5. Sets `X-Request-ID` on the outgoing response.

Wire it in `api.main`:

```python
from api.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)
```

This is a hardening task. Until the middleware is in place, the API produces only the access logs uvicorn emits to stderr — which are not JSON, not structured, and not aggregated with the rest of the codebase.

## Request-ID propagation across processes

When the API triggers a daemon via `pg_notify`, the request ID rides in the payload so the daemon's first log line for that work item carries the same `request_id` and a join is possible without timestamps.

- API side: `pg_notify('rss_source_created', source_id || ':' || request_id)` (or a JSON payload — pick one and document here when implementing).
- Daemon side: parse the payload, push `request_id` into the same `request_id_var`, log normally.

This is also a hardening task (as of 2026-05). Until it's wired, daemon logs and API logs cannot be correlated except by `source_id` and timestamp.

## What to log when

For new code, walk this checklist:

1. **External call** (HTTP, DB query that crosses a boundary, LLM inference, file read/write). Log start at DEBUG with the target identifier; log completion at INFO with `elapsed_s`. Log failures at ERROR with `logger.exception(...)`.
2. **Batch loop.** Log one INFO before the loop ("processing N items") and one after ("done: processed=X, skipped=Y, failed=Z"). Per-iteration logs go at DEBUG only.
3. **Daemon lifecycle.** INFO on start with config (`poll_interval`, `block_duration`, etc.), INFO on shutdown. WARNING on reconnect attempts. ERROR on unrecoverable loop crashes.
4. **API endpoint.** Middleware handles request-level logs. Inside a handler, log only what is *not* visible from the middleware line — e.g., a 200 response that internally hit a degraded fallback.
5. **State transitions on persistent rows.** When `content_source.status` changes, log it at INFO with `source_id` and the new status. The DB has the truth; the log makes the *when* discoverable.

## What NOT to log

- **Secrets:** `DATABASE_URL` (contains password), API keys, tokens, `X-User-Email` headers. If accidentally logged, treat as an incident.
- **GSC metrics.** Per `docs/constraints.md` §"Schema invariants", `article_gsc_metric` is reference-only. Logging clicks/impressions/positions leaks them through stdout. Log only that GSC was joined, not the values.
- **Full article body.** `article.first_paragraph` is fine for DEBUG; `article.body_text` (when added) is not. Truncate to 200 chars max if needed for diagnostics.
- **Full embedding vectors.** They are 768 floats. Log dimension and norm if anything.
- **Full LLM prompts in INFO.** Prompts may contain article titles in Bahasa Indonesia that shouldn't show up in operator dashboards. Log prompt length at INFO; full prompt at DEBUG only.

## Local viewing

Logs go to stdout in JSON. To read them in dev:

```bash
docker compose logs -f api | jq -r 'select(.message != null) | "\(.asctime) \(.levelname) \(.name) — \(.message)"'

docker compose logs -f pipeline-daemon | jq 'select(.step != null)'

docker compose logs --tail=200 ingest-worker | jq 'select(.levelname == "ERROR")'
```

For non-JSON lines from libraries that bypass the formatter, `jq` will error — pipe through `jq -R 'fromjson? // .'` to tolerate them.

## Log retention

Prod containers use Docker's `json-file` driver with `max-size: 10m, max-file: 5` (compose `logging:` block — see `docs/docker-sop.md` §"Compose conventions"). That is ~50MB per service on disk before rotation. The `pipeline` CLI also writes a rotating file handler at `${LOG_DIR}/pipeline.log` (10MB × 3) for run-daily — separate from compose log rotation, useful for post-mortem of a one-shot run.

## Specific rules for AI reviewers

- **Reject `print()` in any non-test file.** Rewrite to `logger.<level>(...)`.
- **Reject `logging.basicConfig`** anywhere except inside a test fixture.
- **Verify every new external call has start/end logs with `elapsed_s`.** Cite this SOP by section.
- **When a PR adds a new structured field, verify it was added to the contract table** in this file in the same PR.

## Specific rules for human reviewers

- **Run the dev stack and check log output before approving a logging-touching PR.** A field name typo is invisible in code review and obvious in `jq`.
- **Check that LOG_LEVEL=DEBUG produces useful output, not noise.** If DEBUG floods the stream with per-row logs that don't help diagnosis, downgrade them to a TRACE convention or delete.

## What this SOP does not cover

- **Log aggregation, retention beyond Docker rotation, dashboards, alerts.** Owned externally per `docs/constraints.md`.
- **Metrics or traces.** This codebase emits logs only. If a future feature needs counters or histograms, propose a decision entry in `docs/decisions.md` first.
- **Per-route auth logs.** Auth is upstream (D10). The gateway logs identity decisions; this app does not.
