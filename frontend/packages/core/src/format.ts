// Backend stores naive UTC datetimes; until every endpoint emits an explicit
// `Z` suffix, treat unsuffixed ISO strings as UTC so display in Asia/Jakarta
// is correct. Strings already carrying a timezone are passed through.
function parseIso(iso: string): Date {
  return /Z|[+-]\d{2}:?\d{2}$/.test(iso) ? new Date(iso) : new Date(iso + "Z")
}

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
  const diffMs = Date.now() - parseIso(iso).getTime()
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
  return parseIso(iso).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Jakarta",
  })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  return parseIso(iso).toLocaleString("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  })
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  return parseIso(iso).toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  })
}
