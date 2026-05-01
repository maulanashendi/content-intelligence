import type { ClusterSummary } from "@ei-fe/api"
import { formatScore } from "@ei-fe/core"
import { RecommendationBadge } from "@ei-fe/ui"
import { VelocityBar } from "./velocity-bar.js"

interface ClusterTableProps {
  clusters: ClusterSummary[]
  onRowClick: (id: string) => void
}

function BucketCell({ label, index }: { label: string | null; index: number }) {
  const num = `#${String(index + 1).padStart(4, "0")}`
  return (
    <td>
      <div style={{ fontFamily: "var(--font-serif)", fontSize: 14.5, fontWeight: 500, lineHeight: 1.3 }}>
        {label ?? "—"}
      </div>
      <div className="faint mono" style={{ fontSize: 10.5, marginTop: 2 }}>
        {num} · kluster
      </div>
    </td>
  )
}

export function ClusterTable({ clusters, onRowClick }: ClusterTableProps) {
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Top topic buckets</span>
        <span className="card-meta">sorted by velocity</span>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: "40%" }}>Topik</th>
            <th>Status</th>
            <th style={{ minWidth: 160 }}>Velocity</th>
            <th>Novelty</th>
            <th>Coverage</th>
            <th className="right">Artikel</th>
          </tr>
        </thead>
        <tbody>
          {clusters.map((c, i) => (
            <tr
              key={c.id}
              className="row-clickable"
              onClick={() => onRowClick(c.id)}
            >
              <BucketCell label={c.label} index={i} />
              <td>
                <RecommendationBadge recommendation={c.recommendation} />
              </td>
              <td>
                <VelocityBar velocity={c.trend_velocity} />
              </td>
              <td className="num">{formatScore(c.novelty_score)}</td>
              <td className="num">{formatScore(c.coverage_score)}</td>
              <td className="num right">{c.member_count ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
