declare global {
  interface ImportMeta {
    readonly env: Record<string, string | undefined>
  }
}

const baseUrl = (import.meta.env.BASE_URL ?? "/").replace(/\/$/, "")

export const env = {
  apiBase: import.meta.env["VITE_API_BASE_URL"] ?? `${baseUrl}/api/v1`,
} as const
