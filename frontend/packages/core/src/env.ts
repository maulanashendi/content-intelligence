// Validate import.meta.env at module load with a Zod schema.
// Required: VITE_API_BASE_URL (string, default "/api/v1").
// Throw on invalid env so the app fails fast at boot, not deep in a component.
// Export typed `env` object consumed by @ei-fe/api/client.ts.
