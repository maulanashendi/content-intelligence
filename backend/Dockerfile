# syntax=docker/dockerfile:1.7

# ============ Base image with uv ============
FROM python:3.11-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/
WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ============ External deps only (cache-stable — invalidated by uv.lock, not source) ============
FROM base AS deps
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml        packages/core/pyproject.toml
COPY packages/api/pyproject.toml         packages/api/pyproject.toml
COPY packages/ingest/pyproject.toml      packages/ingest/pyproject.toml
COPY packages/embedding/pyproject.toml   packages/embedding/pyproject.toml
COPY packages/clustering/pyproject.toml  packages/clustering/pyproject.toml
COPY packages/labeling/pyproject.toml    packages/labeling/pyproject.toml
COPY packages/scoring/pyproject.toml     packages/scoring/pyproject.toml
COPY packages/pipeline/pyproject.toml    packages/pipeline/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-workspace --no-dev --frozen

# ============ API build — add source, install workspace packages ============
FROM deps AS api-build
COPY packages/core/src    packages/core/src
COPY packages/api/src     packages/api/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package api --no-dev --frozen

FROM python:3.11-slim AS api
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=api-build /app/.venv         /app/.venv
COPY --from=api-build /app/packages      /app/packages
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============ API dev — venv only, source via bind mount ============
FROM python:3.11-slim AS api-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=api-build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--reload-dir", "/app/packages/core/src", \
     "--reload-dir", "/app/packages/api/src"]

# ============ Ingest build — add source, install workspace packages ============
FROM deps AS ingest-build
COPY packages/core/src    packages/core/src
COPY packages/ingest/src  packages/ingest/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package ingest --no-dev --frozen

FROM python:3.11-slim AS ingest
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=ingest-build /app/.venv     /app/.venv
COPY --from=ingest-build /app/packages  /app/packages
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
CMD ["python", "-m", "ingest.cli", "serve"]

# ============ Ingest dev — venv only, source via bind mount ============
FROM python:3.11-slim AS ingest-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=ingest-build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
CMD ["python", "-m", "ingest.cli", "serve"]

# ============ Pipeline build — full ML stack ============
FROM deps AS pipeline-build
# Chromium system dependencies required by Playwright (fallback scraper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*
COPY packages/core/src        packages/core/src
COPY packages/ingest/src      packages/ingest/src
COPY packages/embedding/src   packages/embedding/src
COPY packages/clustering/src  packages/clustering/src
COPY packages/labeling/src    packages/labeling/src
COPY packages/scoring/src     packages/scoring/src
COPY packages/pipeline/src    packages/pipeline/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package pipeline --no-dev --frozen
ENV PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers
RUN .venv/bin/playwright install chromium

FROM python:3.11-slim AS pipeline
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=pipeline-build /app/.venv              /app/.venv
COPY --from=pipeline-build /app/packages           /app/packages
COPY --from=pipeline-build /app/playwright-browsers /app/playwright-browsers
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers
ENTRYPOINT ["python", "-m", "pipeline.cli"]
CMD ["run-daily"]

# ============ Pipeline dev — venv only, source via bind mount ============
FROM python:3.11-slim AS pipeline-dev
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=pipeline-build /app/.venv               /app/.venv
COPY --from=pipeline-build /app/playwright-browsers  /app/playwright-browsers
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    PLAYWRIGHT_BROWSERS_PATH=/app/playwright-browsers
ENTRYPOINT ["python", "-m", "pipeline.cli"]
CMD ["run-daily"]
