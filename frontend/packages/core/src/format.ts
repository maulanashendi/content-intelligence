export function formatScore(v: number | null | undefined): string {
  if (v == null) return "—"
  return (v * 100).toFixed(0) + "%"
}

export function formatVelocity(v: number | null | undefined): string {
  if (v == null) return "—"
  return v.toFixed(1)
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—"
  const diffMs = Date.now() - new Date(iso).getTime()
  const diffMins = Math.floor(diffMs / 60_000)
  if (diffMins < 1) return "baru saja"
  if (diffMins < 60) return `${diffMins}m lalu`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}j lalu`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}h lalu`
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Jakarta",
  })
}
