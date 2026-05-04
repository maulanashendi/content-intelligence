# Docker SOP

This is the standard procedure for any change to Docker artifacts in Editor Intelligence — Dockerfile, compose, `.dockerignore`, runtime images. It is written for AI agents and human contributors. Follow it for every Docker-touching PR.

The SOP is opinionated on purpose. It exists because Docker drift is silent: a working `docker compose up` hides cache misses, missing healthchecks, and root-owned containers until the next rebuild or the next prod incident.

## When this applies

- Any change to `backend/Dockerfile`, `backend/docker-compose.yml`, `backend/docker-compose.prod.yml`, `backend/.dockerignore`, or `frontend/Dockerfile`.
- Any change that adds a new long-running process, new top-level dependency, or new build step.
- Any change to `pyproject.toml`, `uv.lock`, or workspace-package `pyproject.toml` files (these invalidate the Docker dep cache — verify the change is intentional).

## Build prerequisites

- BuildKit is required. The Dockerfile uses `# syntax=docker/dockerfile:1.7` and `--mount=type=cache`. Set `DOCKER_BUILDKIT=1` in shells and CI. Compose v2 (`docker compose`, not `docker-compose`) enables BuildKit by default.
- Build from `backend/` (the build context). `context: .` in compose files refers to `backend/`.

## Layer-cache rules

These rules keep the dependency layer stable across edits to source code. Breaking them increases rebuild time from seconds to minutes.

1. **Lock files copy first.** The `deps` stage copies `pyproject.toml`, `uv.lock`, and every workspace package's `pyproject.toml` *before* running `uv sync`. Source files (`packages/<mod>/src/`) must NOT appear in `deps`.
2. **`uv sync --no-install-workspace --no-dev --frozen`** runs in `deps`. This installs external deps only. Workspace packages are installed in their per-target `*-build` stage, after source is copied.
3. **Source copies live in `*-build` stages only.** Each runtime image (`api`, `ingest`, `pipeline`) has a corresponding `*-build` stage that copies `packages/core/src` plus the module's own `src/`, then runs `uv sync --package <module> --no-dev --frozen`.
4. **Cache mount on every `uv sync`.** `RUN --mount=type=cache,target=/root/.cache/uv uv sync ...` reuses the uv download cache across builds.

To diagnose a cache miss: `docker compose build api 2>&1 | grep -E '(CACHED|RUN)'`. If `RUN ... uv sync --no-install-workspace` is not `CACHED` after the first build with no `pyproject.toml`/`uv.lock` change, the layer order is wrong.

## Multi-stage targets

The Dockerfile defines exactly these stages. Each runtime concern (api, ingest, pipeline) has a build/runtime/dev triple.

| Stage           | Purpose                                                          | Used by                              |
| --------------- | ---------------------------------------------------------------- | ------------------------------------ |
| `base`          | python:3.11-slim + build tools + uv                              | All build stages                     |
| `deps`          | External deps installed (no workspace packages)                  | Every `*-build` stage                |
| `api-build`     | `deps` + core + api source + workspace install                   | `api`, `api-dev`                     |
| `api`           | python:3.11-slim runtime, libpq5, venv copied from build         | docker-compose.prod.yml api          |
| `api-dev`       | Same runtime image but venv-only (source bind-mounted)           | docker-compose.yml api               |
| `pipeline-build`| `deps` + core + 5 ML modules + pipeline source + workspace install| `pipeline`, `pipeline-dev`           |
| `pipeline`      | Runtime, ENTRYPOINT `python -m pipeline.cli`, default `run-daily`| pipeline + pipeline-daemon (prod)    |
| `pipeline-dev`  | Venv-only, source bind-mounted                                   | pipeline + pipeline-daemon (dev)     |

The previous `ingest` / `ingest-dev` stages have been removed (D24). The `pipeline` image absorbs ingest's runtime concerns; the `ingest` workspace package is still installed as a dependency of `pipeline` but no longer ships its own runtime image.

**Rule:** any new long-running process gets its own build/runtime/dev triple. Do not hijack an existing target.

## Image-size budgets

| Image      | Budget  | Source                                                              |
| ---------- | ------- | ------------------------------------------------------------------- |
| `api`      | ≤ 250MB | No torch, no transformers (D1, D6)                                  |
| `pipeline` | ≤ 6GB   | sentence-transformers + llama-cpp + sklearn + feedparser + httpx (D24 absorbed ingest runtime) |

Check with `docker images | grep editor-intelligence`. If a runtime image exceeds budget, find and remove the leaked dependency before merging — do not raise the budget.

## Required runtime hardening

These are required for both dev and prod targets unless explicitly justified.

- **Non-root user.** Every runtime stage (`api`, `pipeline`, and their `-dev` variants) must run as `USER app`. Add `RUN useradd -r -u 1000 app && chown -R app:app /app` after copying the venv. *Current state (as of 2026-05): missing in all runtime stages — flagged as a hardening task.*
- **`libpq5` only.** No `build-essential` or `libpq-dev` in runtime stages. Build tooling stays in `base`/`deps`.
- **`PYTHONUNBUFFERED=1`** in every runtime stage. Required for log lines to flush in real time (see `docs/logging-sop.md`).
- **`HF_HOME=/models`** in pipeline stages only. The `hfcache` volume mounts here.
- **No `apt-get upgrade`** in any stage. Pin to the base image's package set.

## Healthchecks

Required in compose for every long-running service.

```yaml
api:
  healthcheck:
    test: ["CMD-SHELL", "python -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8000/api/v1/health\").read()'"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 10s

pipeline-daemon:
  healthcheck:
    test: ["CMD-SHELL", "pgrep -f 'pipeline.cli serve' >/dev/null"]
    interval: 30s
    timeout: 5s
    retries: 3
```

`postgres` already has `pg_isready`. *Current state (as of 2026-05): api/ingest/pipeline missing healthchecks in both compose files — flagged as a hardening task.*

## Compose conventions

### Dev (`docker-compose.yml`)

- Bind-mounts `./packages:/app/packages` on api, pipeline-daemon, pipeline so source edits are live.
- `api` exposes `8000:8000` (no localhost binding — IDE access from host).
- `postgres` exposes `5433:5432` (host port 5433 to avoid colliding with a host-native Postgres).
- `pipeline` runs only with `--profile manual` (one-shot CLI).
- Build target is the `*-dev` variant.

### Prod (`docker-compose.prod.yml`)

- No bind mounts. Source is baked into the image.
- All required env vars use `${VAR:?VAR is required}`. Optional ones use `${VAR:-default}`.
- `api` binds to `127.0.0.1:8000:8000` — assumes a reverse proxy on the host. Do not expose to `0.0.0.0`.
- `postgres` is not port-published in prod.
- Every service has `restart: always`.
- Every service has `logging: { driver: json-file, options: { max-size: 10m, max-file: 5 } }` (see `docs/logging-sop.md` for log content rules; this section governs the file rotation mechanism).
- `pipeline-daemon` has `deploy.resources.limits.memory: 3g`. `pipeline` (manual) has no limit so a manual one-shot can use full RAM if needed.

### `pipeline-daemon` vs `pipeline`

Both build from the `pipeline` target (prod) or `pipeline-dev` (dev). They differ only in command:

- `pipeline-daemon`: `command: ["serve"]` — long-running. Owns reactive ingest+embed, the `rss_source_created` listener, the `pipeline_cluster_label_score_requested` listener, and the in-process daily scheduler (D24).
- `pipeline`: ENTRYPOINT default `run-daily` — one-shot manual runs (`docker compose --profile manual run --rm pipeline ingest`).

Do not merge them. They serve different lifecycles.

## `.dockerignore` rules

The current `backend/.dockerignore` is the canonical list. When adding entries:

- Always exclude: `.git`, `.venv`, `venv`, `__pycache__`, `*.pyc`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.coverage`, `htmlcov`, `**/tests/`, `docs/`, `template-fe/`, `*.md`, `.env`, `.env.*`, `.vscode`, `.idea`, `.DS_Store`, `models/`, `hf_cache/`, `.cache/`, `*.log`.
- Never exclude: `.env.example` (`!.env.example`), workspace package READMEs (`!packages/**/*.md`).
- New top-level directories that should not enter the image must be added explicitly. Check with `docker build --no-cache -f Dockerfile . --progress=plain 2>&1 | grep 'transferring context'` — if the context size jumps, something new is leaking in.

The frontend has no `.dockerignore` today. Add `frontend/.dockerignore` excluding `node_modules`, `dist`, `.bun`, `.git`, `*.log` before the next frontend image build.

## Frontend Dockerfile (known issue, as of 2026-05)

`frontend/Dockerfile` defines `dev` and `prod` targets, but the `prod` target runs `bun run dev --host` on port 5173 — same as dev. This is wrong: production must run a built artifact, not the Vite dev server.

Required state for the `prod` target (hardening task, separate PR):

```dockerfile
FROM base AS prod-build
COPY package.json bun.lock tsconfig*.json ./
COPY packages/ ./packages/
RUN bun install --frozen-lockfile
WORKDIR /app/packages/app
RUN bun run build

FROM oven/bun:1 AS prod
WORKDIR /app
COPY --from=prod-build /app/packages/app/dist /app/dist
RUN useradd -r -u 1000 app && chown -R app:app /app
USER app
EXPOSE 3000
CMD ["bun", "run", "--bun", "serve", "/app/dist"]
```

Until this is fixed, the prod target must not be deployed.

## Troubleshooting

| Symptom                                      | Likely cause                                                          | Fix                                                          |
| -------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------ |
| `uv sync` re-runs every build                | Source copied before `pyproject.toml`/`uv.lock`                       | Move `COPY pyproject.toml uv.lock` before any `COPY src`     |
| Image grew by hundreds of MB unexpectedly    | New runtime dep, or build tool leaked into runtime stage              | `docker history <image>` and inspect the offending layer     |
| Cache mount has no effect                    | BuildKit not enabled                                                  | `DOCKER_BUILDKIT=1` or compose v2                            |
| Bind-mounted source not appearing in container| Wrong target (forgot `-dev`) or stale image                          | Rebuild with `docker compose build --no-cache <service>`     |
| `pip` / `uv` SSL errors during build         | Network proxy in dev environment                                      | Pass build args, do not bake into Dockerfile                 |
| Container exits immediately                  | Missing env var (compose `${VAR:?...}` failed)                        | Check `docker compose config` and the `.env.prod` file       |

## What this SOP does not cover

- **Production orchestration** (Kubernetes, Swarm, ECS). Per `docs/constraints.md`, deploy infra is owned externally. This SOP covers the images and the local compose composition only.
- **TLS / reverse proxy / load balancer.** The reverse proxy on the host terminates TLS and routes to `127.0.0.1:8000`. Configuration of that proxy is owned by the deploy team.
- **CI/CD pipelines.** Building and pushing images in CI is owned by the deploy team. Local build correctness is enforced here.
- **Secret management.** `.env.prod` is gitignored; the deploy team owns secret distribution. Do not bake secrets into images.
- **Log content** (what to log, levels, structured fields). See `docs/logging-sop.md`.
- **Running the stack day-to-day** (start/stop/exec/migrations). See `docs/operations-sop.md`.

## Specific rules for AI reviewers

- **Never approve a Dockerfile change without rebuilding both dev and prod targets.** `docker compose build` and `docker compose -f docker-compose.prod.yml build`.
- **Always check image size after a Dockerfile change.** Compare against the budget table.
- **Always verify cache hits on the second build.** A change that breaks layer cache is a Required finding.
- **Cite this SOP by section** (e.g., "Per `docs/docker-sop.md` §Layer-cache rules, source copies must live in `*-build` stages only").

## Specific rules for human reviewers

- **Smoke-test bind-mounted source reload before approving a `*-dev` change.** Edit a file in `packages/<mod>/src/` and confirm the change appears in the running container.
- **When approving prod-only changes, build with `--no-cache` once.** Cached builds can hide a broken layer order that only surfaces on a clean machine.
