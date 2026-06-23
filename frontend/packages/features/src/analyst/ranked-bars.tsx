const NEED_COLORS: Record<string, string> = {
  "update me": "oklch(0.60 0.12 230)",
  "help me": "oklch(0.62 0.13 155)",
  "educate me": "oklch(0.55 0.15 262)",
  "give me perspective": "oklch(0.58 0.14 300)",
  "inspire me": "oklch(0.60 0.13 45)",
  "divert me": "oklch(0.62 0.12 180)",
}

const NEED_LABELS: Record<string, string> = {
  "update me": "Update me",
  "help me": "Help me",
  "educate me": "Educate me",
  "give me perspective": "Give me perspective",
  "inspire me": "Inspire me",
  "divert me": "Divert me",
}

function needColor(need: string | undefined): string {
  if (!need) return "var(--accent)"
  return NEED_COLORS[need.toLowerCase()] ?? "var(--accent)"
}

function needLabel(need: string | undefined): string {
  if (!need) return ""
  return NEED_LABELS[need.toLowerCase()] ?? need
}

export function RankedBars({
  rows,
  valueCol,
  labelCol,
  needCol,
}: {
  rows: Record<string, unknown>[]
  valueCol: string
  labelCol: string
  needCol?: string
}) {
  const max = rows.reduce((m, r) => Math.max(m, Number(r[valueCol]) || 0), 0) || 1
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((r, i) => {
        const v = Number(r[valueCol]) || 0
        const need = needCol ? String(r[needCol] ?? "") : undefined
        const color = needColor(need)
        const label = needLabel(need)
        return (
          <div key={i} className="flex flex-col gap-1">
            <div className="flex justify-between items-baseline gap-2.5">
              <span className="text-[12.5px] min-w-0 truncate" style={{ color: "var(--fg)", fontFamily: "var(--font-sans)" }}>
                {String(r[labelCol] ?? "—")}
                {label && (
                  <>
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full mx-1.5 align-middle"
                      style={{ background: color, flexShrink: 0 }}
                    />
                    <span className="text-[10.5px]" style={{ fontFamily: "var(--font-sans)", color: "var(--fg-faint)" }}>
                      {label}
                    </span>
                  </>
                )}
              </span>
              <span className="text-[11.5px] tabular-nums shrink-0" style={{ fontFamily: "var(--font-mono)", color: "var(--fg)" }}>
                {v.toLocaleString("id-ID")}
              </span>
            </div>
            <div className="h-2 rounded-[3px] overflow-hidden" style={{ background: "var(--bg-sunken)" }}>
              <span
                className="block h-full rounded-[3px] transition-[width] duration-700"
                style={{ width: `${(v / max) * 100}%`, background: color }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
