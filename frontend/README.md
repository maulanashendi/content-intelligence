# Editor Intelligence — Frontend

Bun workspace, Vite SPA. See `docs/frontend.md` (repo root) for full architecture.

## Quick start

```bash
bun install
bun run dev      # @ei-fe/app on http://localhost:5173
bun test
bun run build    # output: packages/app/dist
bun run gen:api  # regenerate packages/api/src/generated.ts from BE openapi
```

## Packages

- `@ei-fe/core` — env, tokens, types, formatters, errors
- `@ei-fe/api` — fetch wrapper, generated types, Zod schemas, TanStack Query hooks
- `@ei-fe/ui` — shadcn primitives, layout, states, icons, Tailwind preset
- `@ei-fe/features` — morning, cluster-detail, deferred views
- `@ei-fe/app` — Vite shell, providers, routes
