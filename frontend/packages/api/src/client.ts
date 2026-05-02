import { z } from "zod"
import { ApiError, env } from "@ei-fe/core"

async function _handleError(res: Response): Promise<never> {
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

export async function apiGet<TSchema extends z.ZodTypeAny>(
  path: string,
  schema: TSchema,
): Promise<z.infer<TSchema>> {
  const res = await fetch(`${env.apiBase}${path}`, { headers: { Accept: "application/json" } })
  if (!res.ok) await _handleError(res)

  const json: unknown = await res.json()
  const parsed = schema.safeParse(json)
  if (!parsed.success) {
    console.error("[api] schema validation failed", parsed.error.flatten())
    throw new ApiError(0, "Respons API tidak sesuai skema.")
  }
  return parsed.data as z.infer<TSchema>
}

export async function apiPost<TSchema extends z.ZodTypeAny>(
  path: string,
  body: unknown,
  schema: TSchema,
): Promise<z.infer<TSchema>> {
  const res = await fetch(`${env.apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) await _handleError(res)

  const json: unknown = await res.json()
  const parsed = schema.safeParse(json)
  if (!parsed.success) {
    console.error("[api] schema validation failed", parsed.error.flatten())
    throw new ApiError(0, "Respons API tidak sesuai skema.")
  }
  return parsed.data as z.infer<TSchema>
}

export async function apiPatch<TSchema extends z.ZodTypeAny>(
  path: string,
  body: unknown,
  schema: TSchema,
): Promise<z.infer<TSchema>> {
  const res = await fetch(`${env.apiBase}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) await _handleError(res)

  const json: unknown = await res.json()
  const parsed = schema.safeParse(json)
  if (!parsed.success) {
    console.error("[api] schema validation failed", parsed.error.flatten())
    throw new ApiError(0, "Respons API tidak sesuai skema.")
  }
  return parsed.data as z.infer<TSchema>
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${env.apiBase}${path}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  })
  if (!res.ok) await _handleError(res)
}
