import type { ReactNode } from "react"

export function Kpi({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-[10px] p-4" style={{ background: "var(--bg-elev)", border: "1px solid var(--line)" }}>
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.06em] font-medium" style={{ color: "var(--fg-faint)" }}>{label}</div>
      <div className="flex items-baseline gap-2 mt-1.5 text-[26px] font-medium tracking-tight tabular-nums" style={{ color: "var(--fg)" }}>{value}</div>
      {sub && <div className="text-[11px] mt-1" style={{ color: "var(--fg-muted)" }}>{sub}</div>}
    </div>
  )
}
