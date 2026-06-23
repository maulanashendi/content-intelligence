import type { AnalyzeResult } from "@ei-fe/api"
import { orderedUserNeeds, groupedFeatures, analyzeVerdict } from "./data.js"
import { UserNeedsRadar } from "./user-needs-radar.js"
import { UserNeedsBars } from "./user-needs-bars.js"
import { FeatureMatrix } from "./feature-matrix.js"
import { FeedbackCards } from "./feedback-cards.js"
import { ResultCard, Section } from "./result-shell.js"

export function AnalyzeResultCard({ title, result }: { title: string; result: AnalyzeResult }) {
  const needs = orderedUserNeeds(result.user_needs)
  const detected = groupedFeatures(result.features).reduce((s, g) => s + g.detected, 0)
  const verdict = analyzeVerdict(needs, detected)

  return (
    <ResultCard label="Kartu Editorial" meta="16 fitur · 6 kebutuhan">
      {/* Verdict hero */}
      <div className="px-4 pt-4 pb-1">
        <p
          className="text-[11px] font-semibold"
          style={{ fontFamily: "var(--font-sans)", color: "var(--fg-muted)", letterSpacing: "0.01em" }}
        >
          Draf dianalisis
        </p>
        <h3
          className="text-[19px] font-semibold leading-tight mt-1 mb-0"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          {title}
        </h3>
        <p
          className="mt-2 leading-relaxed"
          style={{ fontFamily: "var(--font-serif)", fontSize: "14.5px", color: "var(--fg)" }}
        >
          {verdict.sentence}
        </p>
        <p className="mt-1.5" style={{ color: "var(--fg-faint)", fontSize: "12px" }}>
          <span style={{ fontFamily: "var(--font-mono)" }}>{detected}</span>
          {" dari 16 sinyal editorial terdeteksi."}
        </p>
      </div>

      {/* Kebutuhan pembaca */}
      <Section title="Kebutuhan pembaca">
        <div
          className="grid gap-7 items-center [grid-template-columns:280px_1fr] max-[640px]:[grid-template-columns:1fr]"
        >
          <UserNeedsRadar needs={needs} />
          <UserNeedsBars needs={needs} />
        </div>
      </Section>

      {/* Sinyal editorial */}
      <Section
        title="Sinyal editorial"
        aside={
          <>
            <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-fg)" }}>{detected}</span>
            <span style={{ color: "var(--fg-faint)" }}> / 16 terdeteksi</span>
          </>
        }
      >
        <FeatureMatrix features={result.features} />
      </Section>

      {/* Masukan editorial */}
      <Section title="Masukan editorial">
        <FeedbackCards feedback={result.editorial_feedback} />
      </Section>
    </ResultCard>
  )
}
