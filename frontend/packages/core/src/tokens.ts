export const tokens = {
  colors: {
    bg: "oklch(0.985 0.003 95)",
    bgElev: "oklch(1 0 0)",
    bgSunken: "oklch(0.965 0.004 95)",
    bgHover: "oklch(0.955 0.005 95)",
    fg: "oklch(0.22 0.012 255)",
    fgMuted: "oklch(0.48 0.012 255)",
    fgFaint: "oklch(0.62 0.010 255)",
    fgGhost: "oklch(0.78 0.008 255)",
    line: "oklch(0.92 0.005 95)",
    lineStrong: "oklch(0.86 0.006 95)",
    accent: "oklch(0.55 0.15 262)",
    accentSoft: "oklch(0.93 0.04 262)",
    accentFg: "oklch(0.42 0.16 262)",
    ok: "oklch(0.62 0.13 155)",
    warn: "oklch(0.72 0.15 75)",
    bad: "oklch(0.58 0.18 25)",
    info: "oklch(0.60 0.12 230)",
    persist: "oklch(0.60 0.12 220)",
    maturation: "oklch(0.62 0.12 285)",
    gap: "oklch(0.62 0.13 155)",
  },
  font: {
    sans: '"Geist", system-ui, sans-serif',
    serif: '"Source Serif 4", Georgia, serif',
    mono: '"JetBrains Mono", "Fira Code", monospace',
  },
  radius: {
    base: "6px",
    lg: "10px",
  },
  shadow: {
    sm: "0 1px 2px oklch(0 0 0 / 0.06)",
    md: "0 2px 8px oklch(0 0 0 / 0.08)",
    lg: "0 4px 20px oklch(0 0 0 / 0.10)",
  },
} as const

export type Tokens = typeof tokens
