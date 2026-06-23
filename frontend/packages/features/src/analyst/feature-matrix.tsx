import type { ArticleFeatures } from "@ei-fe/api"
import { groupedFeatures } from "./data.js"

export function FeatureMatrix({ features }: { features: ArticleFeatures }) {
  const groups = groupedFeatures(features)
  return (
    <div
      className="grid gap-3.5 max-[720px]:[grid-template-columns:repeat(2,minmax(0,1fr))] max-[480px]:[grid-template-columns:1fr]"
      style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}
    >
      {groups.map((g) => {
        const detectedFlags = g.flags.filter((f) => f.on)
        const undetectedFlags = g.flags.filter((f) => !f.on)
        return (
          <div key={g.id}>
            {/* Column header */}
            <div
              className="flex justify-between items-baseline pb-1.5 mb-2"
              style={{ borderBottom: "1px solid var(--line)" }}
            >
              <span
                className="text-[11px] font-semibold"
                style={{ fontFamily: "var(--font-sans)", color: "var(--fg-muted)", letterSpacing: "0.02em" }}
              >
                {g.label}
              </span>
              <span className="text-[11px]" style={{ fontFamily: "var(--font-sans)", color: "var(--fg-faint)" }}>
                <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-fg)" }}>{g.detected}</span>
                /{g.flags.length}
              </span>
            </div>

            {/* Detected flags */}
            {detectedFlags.map((f) => (
              <div key={f.key} className="flex gap-2 py-1 items-start">
                <span
                  className="w-[7px] h-[7px] rounded-full shrink-0 mt-[5px]"
                  style={{ background: "var(--accent)", boxShadow: "0 0 0 3px var(--accent-soft)" }}
                />
                <span className="min-w-0">
                  <span
                    className="block text-[12px] leading-tight"
                    style={{ color: "var(--fg)", fontWeight: 500 }}
                  >
                    {f.name}
                  </span>
                  {f.reasoning && (
                    <span
                      className="block text-[11px] mt-0.5 leading-snug"
                      style={{ fontFamily: "var(--font-sans)", color: "var(--fg-faint)" }}
                    >
                      {f.reasoning}
                    </span>
                  )}
                </span>
              </div>
            ))}

            {/* Undetected flags collapsed into one line */}
            {undetectedFlags.length > 0 && (
              <p
                className="text-[11px] mt-1.5 leading-snug"
                style={{ fontFamily: "var(--font-sans)", color: "var(--fg-ghost)" }}
              >
                Tidak terdeteksi: {undetectedFlags.map((f) => f.name).join(", ")}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
