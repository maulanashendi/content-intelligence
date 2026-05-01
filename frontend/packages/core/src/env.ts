declare global {
  interface ImportMeta {
    readonly env: Record<string, string | undefined>
  }
}

export const env = {
  apiBase: import.meta.env["VITE_API_BASE_URL"] ?? "/api/v1",
} as const
