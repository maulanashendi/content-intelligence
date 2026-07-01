import type { UserNeedDatum } from "@ei-fe/ui"

export const CLUSTER_USER_NEED_ORDER = [
  { key: "Update me", label: "Beri tahu" },
  { key: "Keep me engaged", label: "Bikin betah" },
  { key: "Educate me", label: "Edukasi" },
  { key: "Give me perspective", label: "Perspektif" },
  { key: "Inspire me", label: "Inspirasi" },
  { key: "Divert me", label: "Hibur" },
  { key: "Help me", label: "Bantu" },
  { key: "Connect me", label: "Hubungkan" },
] as const

export function distributionToNeeds(
  distribution: Record<string, number> | null,
): UserNeedDatum[] {
  if (!distribution) return []
  const entries = CLUSTER_USER_NEED_ORDER.map((n) => ({
    key: n.key,
    label: n.label,
    count: distribution[n.key] ?? 0,
  }))
  const max = Math.max(0, ...entries.map((e) => e.count))
  if (max === 0) return []
  return entries.map((e) => ({
    key: e.key,
    label: e.label,
    value: Math.round((e.count / max) * 100),
  }))
}
