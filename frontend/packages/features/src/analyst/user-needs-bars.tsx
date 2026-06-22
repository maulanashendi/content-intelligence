interface Need { key: string; label: string; value: number }

export function UserNeedsBars({ needs }: { needs: Need[] }) {
  return (
    <div className="flex flex-col gap-2.5">
      {needs.map((n) => {
        const dom = n.value >= 70
        return (
          <div key={n.key} className="grid items-center gap-2.5" style={{ gridTemplateColumns: "84px 1fr 30px" }}>
            <span className="text-[12px]" style={{ color: "var(--fg)", fontWeight: dom ? 600 : 400 }}>{n.label}</span>
            <span className="h-[7px] rounded-[3px] overflow-hidden" style={{ background: "var(--bg-sunken)", border: "1px solid var(--line)" }}>
              <span className="block h-full rounded-[2px] transition-[width] duration-700"
                style={{ width: `${n.value}%`, background: dom ? "linear-gradient(90deg, var(--accent), oklch(0.45 0.18 285))" : "var(--accent)" }} />
            </span>
            <span className="text-[11.5px] text-right tabular-nums" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-muted)" }}>{n.value}</span>
          </div>
        )
      })}
    </div>
  )
}
