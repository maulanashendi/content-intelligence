import type { AnalyzeResult } from "@ei-fe/api"
import { orderedUserNeeds, groupedFeatures } from "./data.js"
import { UserNeedsRadar } from "./user-needs-radar.js"
import { UserNeedsBars } from "./user-needs-bars.js"
import { FeatureMatrix } from "./feature-matrix.js"
import { FeedbackCards } from "./feedback-cards.js"
import { ResultCard, Section } from "./result-shell.js"

export function AnalyzeResultCard({ title, result }: { title: string; result: AnalyzeResult }) {
  const needs = orderedUserNeeds(result.user_needs)
  const detected = groupedFeatures(result.features).reduce((s, g) => s + g.detected, 0)

  return (
    <ResultCard kicker="Kartu Editorial" meta={`16 fitur · 6 kebutuhan`}>
      <div className="px-4 pt-3.5 pb-1">
        <div className="text-[10px] uppercase tracking-[0.06em]" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>draf dianalisis</div>
        <h3 className="text-[18px] font-semibold leading-tight mt-1 mb-0" style={{ fontFamily: "var(--font-serif)" }}>{title}</h3>
      </div>

      <Section title="Kebutuhan Pembaca · sidik jari editorial">
        <div className="grid gap-4 items-center" style={{ gridTemplateColumns: "248px 1fr" }}>
          <div className="flex flex-col items-center gap-1">
            <UserNeedsRadar needs={needs} />
            <span className="text-[10px]" style={{ fontFamily: "var(--font-mono)", color: "var(--fg-faint)" }}>bentuk = profil · angka di kanan</span>
          </div>
          <UserNeedsBars needs={needs} />
        </div>
      </Section>

      <Section title={<>16 Fitur Editorial · <span style={{ color: "var(--accent-fg)" }}>{detected} terdeteksi</span></>}>
        <FeatureMatrix features={result.features} />
      </Section>

      <Section title="Masukan Editorial">
        <FeedbackCards feedback={result.editorial_feedback} />
      </Section>
    </ResultCard>
  )
}
