FROM oven/bun:1
WORKDIR /app
COPY package.json bun.lock tsconfig*.json ./
COPY packages/ ./packages/
RUN bun install --frozen-lockfile
WORKDIR /app/packages/app
EXPOSE 5173
CMD ["bun", "run", "dev", "--host"]
