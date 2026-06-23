import type { ReactNode } from "react"

export function ResultCard({ label, meta, children }: { label: string; meta?: string; children: ReactNode }) {
  return (
    <div
      className="rounded-[var(--radius-lg)] overflow-hidden"
      style={{ background: "var(--bg-elev)", border: "1px solid var(--line)", boxShadow: "var(--shadow-sm)" }}
    >
      <div className="flex items-center px-4 py-3" style={{ borderBottom: "1px solid var(--line)" }}>
        <span
          className="text-[11.5px] font-semibold"
          style={{ fontFamily: "var(--font-sans)", color: "var(--fg-muted)", letterSpacing: "0.02em" }}
        >
          {label}
        </span>
        {meta && (
          <span
            className="ml-auto text-[11px]"
            style={{ fontFamily: "var(--font-sans)", color: "var(--fg-faint)" }}
          >
            {meta}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

export function Section({
  title,
  aside,
  children,
  noBorder,
}: {
  title: ReactNode
  aside?: ReactNode
  children: ReactNode
  noBorder?: boolean
}) {
  return (
    <div className="p-4" style={noBorder ? undefined : { borderTop: "1px solid var(--line)" }}>
      <div className="flex justify-between items-baseline mb-3">
        <p
          className="text-[11px] font-semibold"
          style={{ fontFamily: "var(--font-sans)", color: "var(--fg-muted)", letterSpacing: "0.02em" }}
        >
          {title}
        </p>
        {aside && (
          <span
            className="text-[11px]"
            style={{ fontFamily: "var(--font-sans)", color: "var(--fg-faint)" }}
          >
            {aside}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}
