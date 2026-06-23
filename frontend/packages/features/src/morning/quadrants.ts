import type { QuadrantSummary } from "@ei-fe/api"

export type Quadrant = keyof Omit<QuadrantSummary, "total">

export interface QuadrantDef {
  key: Quadrant
  emoji: string
  label: string
  sub: string
  action: string
  description: string
  bg: string
  activeBg: string
  border: string
  activeBorder: string
  countColor: string
  highlight?: boolean
}

export const QUADRANTS: QuadrantDef[] = [
  {
    key: "opportunity",
    emoji: "🔥",
    label: "Peluang",
    sub: "Dicari, belum ditulis",
    action: "Tulis sekarang",
    description:
      "Topik ini sedang banyak dicari di luar — tren aktif, kompetitor giat menulis — tapi Tempo belum punya liputannya atau sangat tipis. Ini celah kompetitif yang nyata: editor lain sudah bergerak, pembaca sudah mencarinya.",
    bg: "var(--warn-soft)",
    activeBg: "var(--warn)",
    border: "var(--warn)",
    activeBorder: "var(--warn)",
    countColor: "var(--warn)",
    highlight: true,
  },
  {
    key: "winning",
    emoji: "✅",
    label: "Menang",
    sub: "Dicari, sudah kuat",
    action: "Pertahankan",
    description:
      "Topik ini sudah kuat di kedua sisi: banyak dicari di luar dan Tempo punya liputan yang bagus. Pertahankan konsistensi publikasi. Memperdalam atau memperbarui artikel yang ada bisa memaksimalkan potensi.",
    bg: "var(--ok-soft)",
    activeBg: "var(--ok)",
    border: "var(--ok)",
    activeBorder: "var(--ok)",
    countColor: "var(--ok)",
  },
  {
    key: "ignore",
    emoji: "💤",
    label: "Abaikan",
    sub: "Sepi, belum ditulis",
    action: "Tidak mendesak",
    description:
      "Topik ini sepi dari sisi eksternal — sedikit tren, sedikit kompetitor — dan Tempo belum meliputnya. Tidak ada urgensi editorial. Bisa dikerjakan belakangan atau tidak sama sekali jika ada topik lebih penting.",
    bg: "var(--bg-sunken)",
    activeBg: "var(--line-strong)",
    border: "var(--line)",
    activeBorder: "var(--line-strong)",
    countColor: "var(--fg-muted)",
  },
  {
    key: "evergreen",
    emoji: "🪦",
    label: "Evergreen",
    sub: "Sepi, sudah kuat",
    action: "Biarkan bekerja",
    description:
      "Topik ini tidak sedang trending, tapi Tempo punya liputan yang solid di mesin pencari. Biarkan bekerja sendiri — artikel sudah mendapat trafik organik. Pertimbangkan refresh hanya jika ada angle baru yang signifikan.",
    bg: "var(--info-soft)",
    activeBg: "var(--info)",
    border: "var(--info)",
    activeBorder: "var(--info)",
    countColor: "var(--info)",
  },
]

export const TOO_EARLY_DEF = {
  key: "too_early" as Quadrant,
  emoji: "⏳",
  label: "Pantau Besok",
  action: "Tunggu data GSC",
  description:
    "Tempo sudah punya artikel untuk topik ini, tapi data Google Search Console-nya belum tersedia — artikel terlalu baru (GSC butuh 1–3 hari untuk mencerminkan performa). Cek besok untuk melihat apakah artikel mendapat trafik yang signifikan.",
  border: "var(--line)",
  activeBorder: "var(--accent)",
  countColor: "var(--fg-muted)",
}

export const QUADRANT_BY_KEY: Record<string, QuadrantDef | typeof TOO_EARLY_DEF> = {
  ...Object.fromEntries(QUADRANTS.map((q) => [q.key, q])),
  too_early: TOO_EARLY_DEF,
}
