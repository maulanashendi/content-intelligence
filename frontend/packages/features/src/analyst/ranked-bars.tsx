export function RankedBars({ rows, valueCol, labelCol }: { rows: Record<string, unknown>[]; valueCol: string; labelCol: string }) {
  const max = rows.reduce((m, r) => Math.max(m, Number(r[valueCol]) || 0), 0) || 1
  return (
    <div className="flex flex-col gap-2.5">
      {rows.map((r, i) => {
        const v = Number(r[valueCol]) || 0
        return (
          <div key={i} className="flex flex-col gap-1">
            <div className="flex justify-between items-baseline gap-2.5">
              <span className="text-[12.5px]" style={{ color: "var(--fg)" }}>{String(r[labelCol] ?? "—")}</span>
              <span className="text-[11.5px] tabular-nums" style={{ fontFamily: "var(--font-mono)", color: "var(--fg)" }}>{v.toLocaleString("id-ID")}</span>
            </div>
            <div className="h-2 rounded-[3px] overflow-hidden" style={{ background: "var(--bg-sunken)" }}>
              <span className="block h-full rounded-[3px] transition-[width] duration-700" style={{ width: `${(v / max) * 100}%`, background: "var(--accent)" }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
