import type { UserNeedDatum as Need } from "./radar-points.js"

export function UserNeedsBars({ needs }: { needs: Need[] }) {
  return (
    <div className="flex flex-col" style={{ gap: "10px" }}>
      {needs.map((n) => {
        const dom = n.value >= 70
        return (
          <div
            key={n.key}
            className="grid items-center"
            style={{ gridTemplateColumns: "88px 1fr 28px", gap: "10px" }}
          >
            {/* Label: sans, sentence case — NOT mono */}
            <span
              className="text-[12px] leading-none truncate"
              style={{
                fontFamily: "var(--font-sans)",
                color: dom ? "var(--fg)" : "var(--fg-muted)",
                fontWeight: dom ? 600 : 400,
              }}
            >
              {n.label}
            </span>

            {/* Track + fill */}
            <span
              className="overflow-hidden"
              style={{
                height: "7px",
                borderRadius: "4px",
                background: "var(--bg-sunken)",
                border: "1px solid var(--line)",
                display: "block",
              }}
            >
              <span
                className="block h-full transition-[width] duration-700"
                style={{
                  width: `${n.value}%`,
                  borderRadius: "3px",
                  background: dom
                    ? "linear-gradient(90deg, var(--accent), oklch(0.45 0.18 285))"
                    : "var(--accent)",
                }}
              />
            </span>

            {/* Figure: mono, right-aligned */}
            <span
              className="text-right tabular-nums text-[11.5px] leading-none"
              style={{ fontFamily: "var(--font-mono)", color: "var(--fg-muted)" }}
            >
              {n.value}
            </span>
          </div>
        )
      })}
    </div>
  )
}
