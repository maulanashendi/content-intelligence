# syntax=docker/dockerfile:1.7

# ============ Base image with uv ============
FROM python:3.11-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ============ Shared dependency layer ============
FROM base AS deps
COPY pyproject.toml ./
COPY uv.lock* ./
COPY packages/ ./packages/

# ============ API target — lean, no torch ============
FROM deps AS api-build
RUN uv sync --package api --no-dev

FROM python:3.11-slim AS api
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=api-build /app/.venv /app/.venv
COPY --from=api-build /app/packages/core /app/packages/core
COPY --from=api-build /app/packages/api /app/packages/api
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============ Pipeline target — full ML stack ============
FROM deps AS pipeline-build
RUN uv sync --package pipeline --no-dev

FROM python:3.11-slim AS pipeline
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=pipeline-build /app/.venv /app/.venv
COPY --from=pipeline-build /app/packages /app/packages
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models
ENTRYPOINT ["python", "-m", "pipeline.cli"]
CMD ["run-daily"]
