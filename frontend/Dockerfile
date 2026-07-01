FROM oven/bun:1 AS base
WORKDIR /app

FROM base AS dev
COPY package.json bun.lock tsconfig*.json ./
COPY packages/api/package.json      ./packages/api/package.json
COPY packages/app/package.json      ./packages/app/package.json
COPY packages/core/package.json     ./packages/core/package.json
COPY packages/features/package.json ./packages/features/package.json
COPY packages/ui/package.json       ./packages/ui/package.json
RUN bun install --frozen-lockfile
WORKDIR /app/packages/app
EXPOSE 5173
CMD ["bun", "run", "dev", "--host"]

FROM base AS prod-build
COPY package.json bun.lock tsconfig*.json ./
COPY packages/ ./packages/
RUN bun install --frozen-lockfile
WORKDIR /app/packages/app
RUN bun run build

FROM oven/bun:1 AS prod
WORKDIR /app
COPY --from=prod-build /app/packages/app/dist /app/dist
RUN chown -R bun:bun /app
USER bun
EXPOSE 3000
CMD ["bunx", "serve", "-s", "/app/dist", "-l", "3000"]
