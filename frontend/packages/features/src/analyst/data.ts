import type { ArticleFeatures, UserNeedScore } from "@ei-fe/api"
export { radarPoints } from "@ei-fe/ui"

export const USER_NEED_ORDER = [
  { key: "Update me", label: "Beri tahu" },
  { key: "Educate me", label: "Edukasi" },
  { key: "Give me perspective", label: "Perspektif" },
  { key: "Help me", label: "Bantu" },
  { key: "Inspire me", label: "Inspirasi" },
  { key: "Divert me", label: "Hibur" },
] as const

export function orderedUserNeeds(
  scores: UserNeedScore[],
): { key: string; label: string; value: number }[] {
  const max = scores.reduce((m, s) => Math.max(m, s.score), 0)
  const scale = max > 0 && max <= 1 ? 100 : 1
  const byKey = new Map(scores.map((s) => [s.category.toLowerCase(), s.score]))
  return USER_NEED_ORDER.map((n) => {
    const raw = byKey.get(n.key.toLowerCase()) ?? 0
    return { key: n.key, label: n.label, value: Math.round(Math.min(100, Math.max(0, raw * scale))) }
  })
}

export const FEATURE_ANCHORS: { id: string; label: string; keys: string[] }[] = [
  { id: "time", label: "Waktu & Peristiwa", keys: ["f01_breaking", "f02_live_developing", "f03_timeless"] },
  { id: "depth", label: "Kedalaman & Konteks", keys: ["f04_explanatory", "f05_data_investigative", "f06_author_voice", "f07_depth_analysis", "f08_expert_quotes"] },
  { id: "emotion", label: "Emosi", keys: ["f09_emotional_positive", "f10_conflict_tragedy", "f11_light_humor"] },
  { id: "action", label: "Aksi & Format", keys: ["f12_actionable_steps", "f13_collective_call", "f14_community_identity", "f15_listicle_format", "f16_social_buzz"] },
]

const FEATURE_LABELS: Record<string, string> = {
  f01_breaking: "Breaking / spot news",
  f02_live_developing: "Live / berkembang",
  f03_timeless: "Evergreen",
  f04_explanatory: "Explainer",
  f05_data_investigative: "Data / investigatif",
  f06_author_voice: "Suara penulis / opini",
  f07_depth_analysis: "Analisis dampak",
  f08_expert_quotes: "Kutipan ahli",
  f09_emotional_positive: "Positif / inspiratif",
  f10_conflict_tragedy: "Konflik / tragedi",
  f11_light_humor: "Ringan / humor",
  f12_actionable_steps: "Langkah praktis",
  f13_collective_call: "Ajakan kolektif",
  f14_community_identity: "Identitas komunitas",
  f15_listicle_format: "Listicle",
  f16_social_buzz: "Viral sosial",
}

export function featureLabel(key: string): string {
  return FEATURE_LABELS[key] ?? key
}

export function groupedFeatures(features: ArticleFeatures) {
  const f = features as unknown as Record<string, { status: number; reasoning: string }>
  return FEATURE_ANCHORS.map((a) => {
    const flags = a.keys.map((k) => ({
      key: k,
      name: featureLabel(k),
      on: f[k]?.status === 1,
      reasoning: f[k]?.reasoning ?? "",
    }))
    return { id: a.id, label: a.label, flags, detected: flags.filter((x) => x.on).length }
  })
}

const VIEWS_HINTS = ["page_views", "pageviews", "views", "pv", "reads"]

export function inferNumericColumn(rows: Record<string, unknown>[]): string | null {
  const [first] = rows
  if (!first) return null
  const keys = Object.keys(first)
  const isNum = (k: string) => rows.every((row) => typeof row[k] === "number")
  const hinted = keys.find((k) => VIEWS_HINTS.includes(k.toLowerCase()) && isNum(k))
  if (hinted) return hinted
  return keys.find((k) => isNum(k)) ?? null
}

const FILTER_LABELS: Record<string, string> = {
  category: "kategori",
  user_need_category: "kebutuhan",
  min_page_views: "min. views",
  author: "penulis",
  days_lookback: "rentang",
}

export function humanizeFilterKey(key: string): string {
  return FILTER_LABELS[key] ?? key.replace(/_/g, " ")
}

export function activeFilters(
  filters: Record<string, unknown>,
): { key: string; label: string; value: string }[] {
  return Object.entries(filters)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([key, v]) => ({
      key,
      label: humanizeFilterKey(key),
      value: key === "days_lookback" ? `${String(v)} hari` : String(v),
    }))
}

/** Reader-wants phrasing keyed by the need ID label (matches USER_NEED_ORDER[*].label). */
export const PHRASE: Record<string, string> = {
  "Beri tahu": "tahu kabar terbaru",
  "Edukasi": "memahami persoalan",
  "Perspektif": "melihat dari sudut lain",
  "Bantu": "tahu langkah yang harus diambil",
  "Inspirasi": "merasa terinspirasi",
  "Hibur": "terhibur",
}

export function analyzeVerdict(
  needs: { key: string; label: string; value: number }[],
  _detected: number,
): { leadLabel: string; weakestLabel: string; sentence: string } {
  const sorted = [...needs].sort((a, b) => b.value - a.value)
  const [firstSorted, ...restSorted] = sorted
  if (!firstSorted) {
    return { leadLabel: "", weakestLabel: "", sentence: "" }
  }
  const lead = firstSorted
  const weakest = restSorted.at(-1) ?? lead

  // Secondary: 2nd-highest if value ≥ 50 AND within 15 points of lead
  const second = sorted[1]
  const secondary =
    second && second.value >= 50 && lead.value - second.value <= 15 ? second : null

  if (lead.value < 40) {
    return {
      leadLabel: lead.label,
      weakestLabel: weakest.label,
      sentence: `Profil kebutuhan draf ini belum tajam — sinyal tertinggi ada di kebutuhan ${lead.label}.`,
    }
  }

  const leadPhrase = PHRASE[lead.label] ?? lead.label
  const secondPhrase = secondary ? ` dan ${PHRASE[secondary.label] ?? secondary.label}` : ""
  const weakestPhrase = PHRASE[weakest.label] ?? weakest.label

  return {
    leadLabel: lead.label,
    weakestLabel: weakest.label,
    sentence: `Draf ini berbicara paling kuat kepada pembaca yang ingin ${leadPhrase}${secondPhrase} — dan paling lemah saat harus ${weakestPhrase}.`,
  }
}
