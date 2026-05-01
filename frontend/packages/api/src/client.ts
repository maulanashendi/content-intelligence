import { z } from "zod"
import { ApiError, env } from "@ei-fe/core"

export async function apiGet<TSchema extends z.ZodTypeAny>(
  path: string,
  schema: TSchema,
): Promise<z.infer<TSchema>> {
  const url = `${env.apiBase}${path}`
  const res = await fetch(url, { headers: { Accept: "application/json" } })

  if (!res.ok) {
    const requestId = res.headers.get("x-request-id") ?? undefined
    const body = await res.text().catch(() => "")
    let message = `HTTP ${res.status}`
    try {
      const json = JSON.parse(body) as { detail?: string }
      if (json.detail) message = json.detail
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, message, requestId)
  }

  const json: unknown = await res.json()
  const parsed = schema.safeParse(json)
  if (!parsed.success) {
    console.error("[api] schema validation failed", parsed.error.flatten())
    throw new ApiError(0, "Respons API tidak sesuai skema.")
  }
  return parsed.data as z.infer<TSchema>
}
