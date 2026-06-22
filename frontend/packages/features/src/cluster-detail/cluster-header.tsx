import { useNavigate } from "react-router-dom"
import type { ClusterDetail } from "@ei-fe/api"
import { formatVelocity } from "@ei-fe/core"
import { SignalBadge, Sparkles } from "@ei-fe/ui"

interface ClusterHeaderProps {
  cluster: ClusterDetail
}

export function ClusterHeader({ cluster }: ClusterHeaderProps) {
  const pct = Math.min(100, Math.max(0, (cluster.trend_velocity ?? 0) * 100))
  const navigate = useNavigate()

  return (
    <div className="card" style={{ margin: "24px 28px" }}>
      <div className="card-head">
        <span className="card-title">Cluster Detail</span>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          {cluster.label && (
            <button
              type="button"
              onClick={() => navigate(`/analyst?title=${encodeURIComponent(cluster.label!)}`)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[6px] text-[12.5px]"
              style={{ color: "var(--fg-muted)", border: "1px solid var(--line)" }}
            >
              <Sparkles size={13} />
              Analisis draf
            </button>
          )}
          <SignalBadge tempoCovered={cluster.tempo_covered} lastInternalDaysAgo={cluster.last_internal_days_ago} underperformed={cluster.underperformed} />
        </div>
      </div>
      <div style={{ padding: "16px 18px" }}>
        <h2
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "22px",
            fontWeight: 500,
            letterSpacing: "-0.015em",
            lineHeight: 1.25,
            margin: "0 0 16px",
            color: "var(--fg)",
          }}
        >
          {cluster.label ?? "Topik tanpa label"}
        </h2>

        <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
          <div className="score-split" style={{ minWidth: 180 }}>
            <span className="score-num">{formatVelocity(cluster.trend_velocity)}</span>
            <div className="score-bar">
              <span className="seg-p" style={{ width: `${pct}%` }} />
            </div>
          </div>
          <div className="score-chip">
            <span className="lab">Kompetitor</span>
            <span className="v">{cluster.competitor_count ?? "—"}</span>
          </div>
          <div className="score-chip">
            <span className="lab">Sinyal Trend</span>
            <span className="v">{cluster.trend_match_count ?? "—"}</span>
          </div>
          {cluster.last_internal_days_ago != null && (
            <div className="score-chip">
              <span className="lab">Ditulis</span>
              <span className="v">{cluster.last_internal_days_ago}h lalu</span>
            </div>
          )}
          <div className="score-chip">
            <span className="lab">Artikel</span>
            <span className="v">{cluster.member_count ?? "—"}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
