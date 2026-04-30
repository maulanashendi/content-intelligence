// Thin fetch wrapper. Single responsibility per call:
//   1. Prepend env.VITE_API_BASE_URL.
//   2. fetch() with default headers (Accept: application/json).
//   3. Parse JSON.
//   4. Validate against a Zod schema passed by caller.
//   5. Throw ApiError on non-2xx OR Zod parse failure.
// No retry (TanStack Query owns retry).
// No interceptors. No auth — gateway handles it (decisions.md D10).
// Export: apiGet<TSchema>(path, schema) → Promise<z.infer<TSchema>>.
