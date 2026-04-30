FROM oven/bun:1
WORKDIR /app
COPY package.json tsconfig*.json ./
COPY packages/ ./packages/
RUN bun install
WORKDIR /app/packages/app
EXPOSE 5173
CMD ["bun", "run", "dev", "--host"]
