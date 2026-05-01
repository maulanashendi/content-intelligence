export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError
}

export function toUserMessage(e: unknown): string {
  if (isApiError(e)) {
    if (e.status === 404) return "Data tidak ditemukan."
    if (e.status >= 500) return "Server sedang bermasalah. Coba lagi nanti."
    return e.message
  }
  if (e instanceof Error) return e.message
  return "Terjadi kesalahan tidak dikenal."
}
