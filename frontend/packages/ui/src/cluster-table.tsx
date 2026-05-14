import { SignalBadge } from "./primitives/badge.js"
import { VelocityBar } from "./primitives/velocity-bar.js"

interface ClusterRow {
  id: string
  label: string | null
  member_count: number | null
  trend_velocity: number | null
  competitor_count: number | null
  trend_match_count: number | null
  tempo_covered: boolean | null
  last_internal_days_ago: number | null
  underperformed: boolean | null
}

interface ClusterTableProps {
  clusters: ClusterRow[]
  onSelect: (id: string) => void
  selected?: string | null
  runAlgorithm?: string | null
  order?: "asc" | "desc"
  onToggleOrder?: () => void
}

export function ClusterTable({
  clusters,
  onSelect,
  selected,
  runAlgorithm,
  order,
  onToggleOrder,
}: ClusterTableProps) {
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Article Clusters</span>
        <span className="card-meta">{clusters.length} kluster</span>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: "36%" }}>Label</th>
            <th>Status</th>
            <th style={{ minWidth: 160 }}>Velocity</th>
            <th>Kompetitor</th>
            <th>Trend</th>
            <th className="right">
              {onToggleOrder ? (
                <button
                  className="btn btn-ghost"
                  style={{ fontSize: 11, padding: "1px 4px", gap: 3 }}
                  onClick={onToggleOrder}
                >
                  Artikel {order === "desc" ? "↓" : "↑"}
                </button>
              ) : (
                "Artikel"
              )}
            </th>
          </tr>
        </thead>
        <tbody>
          {clusters.length === 0 ? (
            <tr>
              <td
                colSpan={6}
                style={{
                  textAlign: "center",
                  padding: "24px 0",
                  color: "var(--fg-faint)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 13,
                }}
              >
                tidak ada
              </td>
            </tr>
          ) : (
            clusters.map((c, i) => (
              <tr
                key={c.id}
                className="row-clickable"
                onClick={() => onSelect(c.id)}
                style={selected === c.id ? { background: "var(--accent-soft)" } : undefined}
              >
                <td>
                  <div style={{ fontFamily: "var(--font-serif)", fontSize: 14.5, fontWeight: 500, lineHeight: 1.3 }}>
                    {c.label ?? "—"}
                  </div>
                  <div className="faint mono" style={{ fontSize: 10.5, marginTop: 2 }}>
                    #{String(i + 1).padStart(4, "0")} · {runAlgorithm ?? "kluster"}
                  </div>
                </td>
                <td>
                  <SignalBadge tempoCovered={c.tempo_covered} lastInternalDaysAgo={c.last_internal_days_ago} underperformed={c.underperformed} />
                </td>
                <td>
                  <VelocityBar velocity={c.trend_velocity} />
                </td>
                <td className="num">{c.competitor_count ?? "—"}</td>
                <td className="num">{c.trend_match_count ?? "—"}</td>
                <td className="num right">{c.member_count ?? "—"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
