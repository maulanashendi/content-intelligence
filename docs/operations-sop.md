# Operations SOP

This is the standard procedure for running, debugging, and supervising Editor Intelligence locally and in dev/prod-like setups. Written for AI agents and humans.

The SOP is opinionated on purpose. Local dev runs in Docker — not host-native `uv run` — so what you see locally matches what runs in production. Drift between host and prod is the most common source of "works on my machine" incidents.

## When this applies

- Day-to-day development: starting/stopping the stack, tailing logs, running migrations, exec'ing into a container.
- Debugging a failing pipeline step or a stuck daemon.
- Adding/disabling a content source.
- Recovering from a missed `pg_notify` or a partial cluster run.

## Always-Docker dev workflow

**Hard rule:** local development uses `docker compose` from `backend/`. Host-native `uv run` is allowed only for:

1. Unit tests against the test database (`uv run pytest packages/<mod>/tests/`).
2. IDE integration (linters, type checking, refactoring, autocomplete).

Reasons:
- Production runs in containers (`docs/docker-sop.md`). Dev parity catches packaging bugs before deploy.
- The HuggingFace cache mounts at `/models` in the container, matching prod. Host caches drift over time.
- Postgres + pgvector versions, locale, and timezone are pinned in the image. Host Postgres is whatever the developer installed.
- The pgvector extension is created by the container init scripts, not by `alembic`.

If you find yourself running `uv run uvicorn ...` against a host Postgres, stop and switch to compose.

### Quickstart

```bash
cd backend
cp .env.example .env                 # only on first checkout
docker compose up -d postgres        # bring DB up first
docker compose run --rm api alembic upgrade head
docker compose up -d                 # api + pipeline-daemon
docker compose logs -f api           # tail
```

Prod uses `docker-compose.prod.yml` and a separate `.env.prod` (gitignored). Build and run from `backend/`:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod build
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## Service map

| Service           | Compose file | Profile  | Image target                | Command default                    | Lifecycle                 |
| ----------------- | ------------ | -------- | --------------------------- | ---------------------------------- | ------------------------- |
| `postgres`        | both         | (always) | `pgvector/pgvector:pg16`    | `postgres`                         | always running            |
| `api`             | both         | (always) | `api` / `api-dev`           | `uvicorn api.main:app ...`         | always running            |
| `pipeline-daemon` | both         | (always) | `pipeline` / `pipeline-dev` | `python -m pipeline.cli serve`     | always running, singleton |
| `pipeline`        | both         | `manual` | `pipeline` / `pipeline-dev` | `python -m pipeline.cli run-daily` | one-shot                  |

The previous standalone `ingest-worker` service has been removed (D24). The merged `pipeline-daemon` now owns every long-running concern: reactive RSS source ingestion, periodic ingest poll loop with reactive embed chaining, the daily cluster + label scheduler tick, and the manual cluster + label trigger.

Connections:
- All services connect to `postgres` over the compose network at `postgres:5432`.
- `api` is the only HTTP-exposed service. Dev: `0.0.0.0:8000`. Prod: `127.0.0.1:8000` (reverse proxy on the host).
- `pipeline-daemon` listens on `pg_notify` channels:
  - `rss_source_created` — new RSS source registered via the API; the daemon fetches it immediately.
  - `pipeline_cluster_label_score_requested` — manual or scheduled cluster + label trigger.
- `pipeline` (manual) shares the `hfcache` volume with `pipeline-daemon` so model weights are downloaded once.

Singletons: `pipeline-daemon` must run as a single replica. Its in-memory immediate-fetch queue is process-local and the cluster lock row in `pipeline_group_lock` assumes one writer. Multiple replicas cause duplicate fetches or concurrent ML runs.

## Daily commands

```bash
# Start full dev stack
docker compose up -d

# Stop everything
docker compose down                              # keeps volumes
docker compose down -v                           # also wipes pgdata + hfcache (destructive)

# Tail one service
docker compose logs -f api
docker compose logs -f pipeline-daemon

# Tail with JSON filtering
docker compose logs -f pipeline-daemon | jq 'select(.step != null)'

# Rebuild after dependency change (Docker layer cache keeps ML wheels stable)
docker compose build api                         # one service
docker compose build                             # all

# Open a shell inside a running container
docker compose exec api bash
docker compose exec postgres psql -U app -d editor_intelligence

# Run a one-shot pipeline step manually (debugging / partial recovery only)
docker compose --profile manual run --rm pipeline ingest
docker compose --profile manual run --rm pipeline embed
docker compose --profile manual run --rm pipeline cluster
docker compose --profile manual run --rm pipeline label
docker compose --profile manual run --rm pipeline score          # disabled in the daemon path; runnable for ad-hoc inspection
docker compose --profile manual run --rm pipeline run-daily      # legacy 5-step run for debugging

# Trigger a cluster + label run from the API (preferred over the manual CLI)
curl -X POST http://localhost:8000/api/v1/pipeline/cluster-label-score

# Run the test suite
docker compose run --rm api pytest packages/api/tests/
```

## Adding/disabling a content source

The flow exercises D19 (source CRUD) and the reactive ingest path absorbed from D20.

```bash
# Add a new RSS feed
curl -X POST http://localhost:8000/api/v1/sources \
  -H 'Content-Type: application/json' \
  -d '{"name": "Example Outlet", "url": "https://example.com/rss", "source_type": "rss"}'

# Verify pg_notify fired and pipeline-daemon picked it up
docker compose logs pipeline-daemon | tail -20
# Expect a line like: "immediate source=Example Outlet ingested N articles"

# Toggle a source off
curl -X PATCH http://localhost:8000/api/v1/sources/<id> \
  -H 'Content-Type: application/json' \
  -d '{"is_enabled": false}'

# Hard delete a source with no articles
curl -X DELETE http://localhost:8000/api/v1/sources/<id>
```

If the immediate fetch did not fire:
1. Check `pipeline-daemon` is running: `docker compose ps`.
2. Confirm the listener attached: grep logs for `pg_notify listener attached channels=['rss_source_created', ...]`.
3. Wait for the next poll cycle (default 600s) — the daemon's periodic ingest run will pick the source up via the standard RSS list.
4. Or run a one-shot ingest from the manual profile: `docker compose --profile manual run --rm pipeline ingest`.

## Recovering from a missed `pg_notify`

`pg_notify` is best-effort. If the consumer was not running when the notification fired, it is lost.

| Channel                                  | Consumer          | Recovery                                                                                                                                                    |
| ---------------------------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rss_source_created`                     | `pipeline-daemon` | Safety net: the daemon's periodic ingest poll catches the new source within `POLL_INTERVAL` (600s). To force immediately: `docker compose --profile manual run --rm pipeline ingest`. |
| `pipeline_cluster_label_score_requested` | `pipeline-daemon` | Re-issue via the API (`POST /api/v1/pipeline/cluster-label-score`), or run `docker compose --profile manual run --rm pipeline cluster && ... label` from the CLI. The daemon's internal scheduler will also fire at 06:00 WIB the next day. |

Single-replica caveat: do not start a second `pipeline-daemon` to "speed up recovery" — it will fetch the same source twice and cause duplicate cluster runs.

## Cluster-run recovery

A failed cluster + label run leaves the system in a partial state. The steps are idempotent at the row level (`is_current` flip is atomic per `cluster_run`; `article_cluster.label` updates by primary key), so re-running is safe.

Diagnose where it died:

```bash
docker compose logs pipeline-daemon | jq 'select(.levelname == "ERROR")'
docker compose logs pipeline-daemon | jq 'select(.step != null)'   # last completed step
```

Re-run from the failing step (manual profile):

```bash
docker compose --profile manual run --rm pipeline cluster
docker compose --profile manual run --rm pipeline label
```

If clustering succeeded but labeling crashed, do not re-run `cluster` — that flips `is_current` and creates a new `cluster_run`. Run only `label` against the existing run.

`scoring` is currently disabled in the daemon (D24). The `score` CLI command still runs but is not part of the production execution path; do not rely on its output.

## Alembic in dev and prod

Schema source of truth: `backend/packages/core/src/core/models.py` (SQLAlchemy ORM). Migrations are autogenerated and committed.

```bash
# Dev: after editing models.py
docker compose run --rm api alembic revision --autogenerate -m "add foo"

# Review the generated SQL by hand. Autogenerate misses enum changes,
# server defaults, and CREATE EXTENSION lines — fix the migration file.

# Apply
docker compose run --rm api alembic upgrade head

# Roll back one revision (dev only)
docker compose run --rm api alembic downgrade -1
```

Prod deploy gating:

1. Build the new image.
2. Stop `api` and `pipeline-daemon`.
3. Run `docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head`.
4. If migration succeeds, start the services.
5. If it fails, do not start the services. Investigate before retrying.

Enum drop gotcha: Postgres does not auto-drop ENUM types when their column is removed. Migrations that add a column with a new ENUM must explicitly `op.execute("DROP TYPE foo")` in `downgrade()`. See `docs/review-sop.md` §"Schema / migrations" for the smoke pattern.

## Pipeline scheduler

The cluster + label run is scheduled inside the daemon, not by host `cron` (D24). The schedule is config-driven via env:

```bash
TIMEZONE=Asia/Jakarta            # IANA tz identifier
CLUSTER_SCHEDULE_HOUR=6          # 0–23
CLUSTER_SCHEDULE_MINUTE=0        # 0–59
```

Default 06:00 WIB. To change the schedule, edit env and restart `pipeline-daemon`. There is no host `cron` or `systemd timer` to touch. Manual API triggers always work regardless of schedule.

## Resource budgets

From `docs/tech-stack.md` §"Resource footprint estimate":

| Process               | Steady RAM | Peak                                      |
| --------------------- | ---------- | ----------------------------------------- |
| Postgres              | ~2 GB      | ~2.5 GB during clustering                 |
| `api`                 | ~150 MB    | ~250 MB                                   |
| `pipeline-daemon`     | ~2.5 GB    | ~3 GB (memory limit) — Embed + LLM loaded |
| `pipeline` (one-shot) | ~3 GB      | ~5 GB during clustering                   |

VPS minimum: **8 GB RAM, 4 vCPU, 50 GB disk.**

## Re-embed migration (SP3)

Use this runbook when switching `EMBEDDING_PROVIDER` from `local` to `api` (or vice-versa) on a live DB. The operation is resumable and idempotent: `reembed` skips articles that already have a valid embedding under the new provider, and `cluster` replaces `is_current` atomically.

**Prerequisites:** `EMBEDDING_API_KEY` and `EMBEDDING_API_MODEL` set in `.env`; `EMBEDDING_PROVIDER=api`.

### Step 1 — Validate (non-destructive; human go/no-go required)

Stop the daemon first — this is mandatory, not optional. The `cluster_label_score` group lock that `reembed` holds only blocks concurrent *cluster* runs; it does NOT stop the daemon's reactive embed cycle, which can interleave new embeddings while `reembed` is deleting and recomputing. Re-embed deletes rows, so a running daemon risks a half-migrated, mixed-provider vector set.

```bash
docker compose stop pipeline-daemon

# Run the validation script against the configured EMBEDDING_PROVIDER
cd backend && ./.venv/bin/python scripts/validate_embeddings.py
```

Read the output signals before proceeding:

| Signal | Expected |
| --- | --- |
| `returned_dims` | **768** — confirms `dimensions=768` param is honoured by OpenRouter |
| `n_clusters` | Comparable to current run (order-of-magnitude check) |
| `noise_ratio` | Not materially worse than current run |
| `sample_titles` | Titles are semantically coherent within each cluster |

**Go/no-go:** if `returned_dims != 768` or cluster quality is clearly degraded, abort — set `EMBEDDING_PROVIDER=local` and restart the daemon. A mismatch in `returned_dims` would corrupt the `vector(768)` column.

### Step 2 — Cutover (after go decision)

```bash
# Bulk re-embed all articles under the new provider (resumable)
docker compose --profile manual run --rm pipeline reembed

# Regenerate clusters from the new vectors
docker compose --profile manual run --rm pipeline cluster

# Restart the daemon (now runs in api embedding mode)
docker compose up -d pipeline-daemon
```

`reembed` is operator-gated and never scheduled. Do not run it while `pipeline-daemon` is up — the group lock prevents concurrent cluster runs, but concurrent embed writes can interleave. Stop the daemon first.

## What this SOP does not cover

- **Production monitoring, alerting, dashboards.** Owned externally per `docs/constraints.md`.
- **TLS termination and reverse proxy configuration.** Owned by the deploy team.
- **Secret rotation.** Owned by the deploy team.
- **Backup / restore of `pgdata`.** Owned by the deploy team.
- **Image build details and layer-cache rules.** See `docs/docker-sop.md`.
- **What to log inside services.** See `docs/logging-sop.md`.
- **PR review process.** See `docs/review-sop.md`.

## Specific rules for AI agents

- **Default to Docker.** When the user reports a bug, reproduce it in `docker compose`, not in `uv run` on the host.
- **Never run `docker compose down -v`** without explicit confirmation. It wipes `pgdata` and `hfcache`.
- **Never start a second `pipeline-daemon`.** It is a singleton.
- **Cite this SOP by section** when recommending a recovery path (e.g., "Per `docs/operations-sop.md` §Cluster-run recovery, do not re-run `cluster`...").

## Specific rules for human operators

- **Tail logs in JSON via `jq`.** Plain `docker compose logs` truncates structured fields.
- **Use `--profile manual` for one-shot pipeline runs.** Without it, `docker compose up` would start the manual `pipeline` service alongside the daemon and double the work.
- **Stop services in reverse-dependency order** when shutting down for maintenance: pipeline-daemon → api → postgres.
