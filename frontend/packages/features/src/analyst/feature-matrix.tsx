import type { ArticleFeatures } from "@ei-fe/api"
import { groupedFeatures } from "./data.js"

export function FeatureMatrix({ features }: { features: ArticleFeatures }) {
  const groups = groupedFeatures(features)
  return (
    <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
      {groups.map((g) => (
        <div key={g.id}>
          <div className="flex justify-between pb-1.5 mb-2" style={{ borderBottom: "1px solid var(--line)" }}>
            <span className="text-[9.5px] uppercase tracking-[0.05em]" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>{g.label}</span>
            <span className="text-[9.5px]" style={{ fontFamily: "var(--font-mono)", color: "var(--accent-fg)" }}>{g.detected}/{g.flags.length}</span>
          </div>
          {g.flags.map((f) => (
            <div key={f.key} className="flex gap-2 py-1 items-start">
              <span className="w-[7px] h-[7px] rounded-full shrink-0 mt-[5px]"
                style={f.on
                  ? { background: "var(--accent)", boxShadow: "0 0 0 3px var(--accent-soft)" }
                  : { background: "var(--bg-sunken)", border: "1px solid var(--line-strong)" }} />
              <span className="min-w-0">
                <span className="block text-[11.5px] leading-tight" style={{ color: f.on ? "var(--fg)" : "var(--fg-ghost)", fontWeight: f.on ? 500 : 400 }}>{f.name}</span>
                {f.on && f.reasoning && (
                  <span className="block text-[9.5px] mt-0.5 leading-snug" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>{f.reasoning}</span>
                )}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
