import type { ClusterDetail } from "@ei-fe/api"
import { formatDateTime } from "@ei-fe/core"

interface GeneratedAnglesCardProps {
  cluster: ClusterDetail
}

export function GeneratedAnglesCard({ cluster }: GeneratedAnglesCardProps) {
  const { what_happened, editorial_angle, parties_involved, bullet_insights, insight_calculated_at } = cluster
  const hasInsight = what_happened || editorial_angle || parties_involved?.length || bullet_insights?.length

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">
          <span className="angle-tag">AI</span>
          {" "}Generated Angles · Bullet Insights
        </span>
        <span className="card-meta">
          {insight_calculated_at ? formatDateTime(insight_calculated_at) : "—"}
        </span>
      </div>

      {!hasInsight ? (
        <div className="ci-list">
          <p style={{ fontSize: 13, color: "var(--fg-muted)", padding: "8px 0" }}>
            Insight belum tersedia — cluster belum dilabeli.
          </p>
        </div>
      ) : (
        <div className="ci-list">
          {what_happened && (
            <div className="ci-block">
              <div className="ci-block-head">
                <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fg-muted)" }}>
                  Peristiwa
                </span>
              </div>
              <p style={{ fontSize: 13, color: "var(--fg)", lineHeight: 1.5, marginTop: 4 }}>
                {what_happened}
              </p>
            </div>
          )}

          {editorial_angle && (
            <div className="ci-block">
              <div className="ci-block-head">
                <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fg-muted)" }}>
                  Sudut Editorial
                </span>
              </div>
              <p style={{ fontSize: 13, color: "var(--fg)", lineHeight: 1.5, marginTop: 4, fontStyle: "italic" }}>
                {editorial_angle}
              </p>
            </div>
          )}

          {parties_involved && parties_involved.length > 0 && (
            <div className="ci-block">
              <div className="ci-block-head">
                <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fg-muted)" }}>
                  Pihak Terlibat
                </span>
              </div>
              <ul className="ci-bullets" style={{ marginTop: 4 }}>
                {parties_involved.map((party: string) => (
                  <li key={party}>{party}</li>
                ))}
              </ul>
            </div>
          )}

          {bullet_insights && bullet_insights.length > 0 && (
            <div className="ci-block">
              <div className="ci-block-head">
                <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fg-muted)" }}>
                  Poin Kunci
                </span>
              </div>
              <ul className="ci-bullets" style={{ marginTop: 4 }}>
                {bullet_insights.map((item: string) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
