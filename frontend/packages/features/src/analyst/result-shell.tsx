import type { ReactNode } from "react"

export function ResultCard({ kicker, meta, children }: { kicker: string; meta?: string; children: ReactNode }) {
  return (
    <div className="rounded-[10px] overflow-hidden" style={{ background: "var(--bg-elev)", border: "1px solid var(--line)", boxShadow: "var(--shadow-sm)" }}>
      <div className="flex items-center gap-2.5 px-4 py-2.5" style={{ borderBottom: "1px solid var(--line)" }}>
        <span className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-[0.06em]" style={{ color: "var(--fg-muted)" }}>
          <span className="w-2 h-2 rounded-full" style={{ background: "linear-gradient(135deg, var(--accent), oklch(0.45 0.18 285))", boxShadow: "0 0 0 2px var(--accent-soft)" }} />
          {kicker}
        </span>
        {meta && <span className="ml-auto text-[11px]" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>{meta}</span>}
      </div>
      {children}
    </div>
  )
}

export function Section({ title, accent, children, noBorder }: { title: ReactNode; accent?: ReactNode; children: ReactNode; noBorder?: boolean }) {
  return (
    <div className="p-4" style={noBorder ? undefined : { borderTop: "1px solid var(--line)" }}>
      <p className="text-[10.5px] font-semibold uppercase tracking-[0.06em] mb-3" style={{ color: "var(--fg-muted)" }}>{title}{accent}</p>
      {children}
    </div>
  )
}
