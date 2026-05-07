FROM oven/bun:1
WORKDIR /app
COPY package.json bun.lock tsconfig*.json ./
COPY packages/api/package.json      ./packages/api/package.json
COPY packages/app/package.json      ./packages/app/package.json
COPY packages/core/package.json     ./packages/core/package.json
COPY packages/features/package.json ./packages/features/package.json
COPY packages/ui/package.json       ./packages/ui/package.json
RUN bun install --frozen-lockfile
COPY packages/ ./packages/
WORKDIR /app/packages/app
EXPOSE 5173
CMD ["bun", "run", "dev", "--host"]
