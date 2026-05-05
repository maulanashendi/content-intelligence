import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useLatestClusterRun, useCurrentClusters, type ClusterRun, type ClusterSummary } from "@ei-fe/api"
import { RecommendationBadge } from "@ei-fe/ui"
import { TrendSignalCard, ArticleClustersCard } from "@ei-fe/features"

/* ── Helpers ──────────────────────────────────────────────────────── */

function parseIso(iso: string): Date {
  return /Z|[+-]\d{2}:?\d{2}$/.test(iso) ? new Date(iso) : new Date(iso + "Z")
}

function fmtTime(iso: string): string {
  return parseIso(iso).toLocaleString("id-ID", {
    day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }) + " WIB"
}

function duration(start: string, end: string | null): string {
  if (!end) return "—"
  const ms = parseIso(end).getTime() - parseIso(start).getTime()
  const s = Math.round(ms / 1000)
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`
}

/* ── Components ───────────────────────────────────────────────────── */

function RunInfoCard({ run }: { run: ClusterRun | undefined }) {
  const [expanded, setExpanded] = useState(false)
  const dur = run ? duration(run.started_at, run.finished_at) : "—"

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <span className="card-title">Cluster Run</span>
        <span className="badge badge-ok" style={{ marginLeft: 0 }}>latest</span>
        <span className="card-meta">{run ? fmtTime(run.started_at) : "—"}</span>
        <span className="faint mono" style={{ fontSize: 11, marginLeft: "auto" }}>
          {dur} · {run?.algorithm ?? "—"} {run?.algorithm_version ?? ""}
        </span>
        <button
          className="btn btn-ghost"
          style={{ fontSize: 11.5, padding: "2px 8px" }}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "tutup" : "params"}
        </button>
      </div>

      <div style={{ padding: "10px 14px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {[
          { label: "Algoritma", value: run?.algorithm?.toUpperCase() ?? "—" },
          { label: "Kluster terbentuk", value: run != null ? String(run.cluster_count) : "—" },
          { label: "Durasi run", value: dur },
          { label: "Selesai", value: run?.finished_at ? fmtTime(run.finished_at) : "—" },
        ].map(({ label, value }) => (
          <div key={label}>
            <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--fg-faint)", fontWeight: 500, marginBottom: 2 }}>
              {label}
            </div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 500 }}>{value}</div>
          </div>
        ))}
      </div>

      {run?.notes && (
        <div style={{ padding: "0 14px 10px", fontSize: 12.5, color: "var(--fg-muted)", fontStyle: "italic", borderTop: "1px solid var(--line)", paddingTop: 8, marginTop: 2 }}>
          {run.notes}
        </div>
      )}

      {expanded && run?.params && (
        <div style={{ borderTop: "1px solid var(--line)", padding: "10px 14px" }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--fg-faint)", marginBottom: 8 }}>
            {run.algorithm?.toUpperCase() ?? "CLUSTER"} params
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {Object.entries(run.params).map(([k, v]) => (
              <div key={k} className="score-chip">
                <span className="lab">{k}</span>
                <span className="v">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


function ClusterInsightPanel({ cluster, run }: { cluster: ClusterSummary | undefined; run: ClusterRun | undefined }) {
  if (!cluster) return null

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="card-head">
        <span className="card-title">Cluster Insight</span>
        {cluster.recommendation && (
          <RecommendationBadge recommendation={cluster.recommendation} />
        )}
      </div>
      <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <p style={{ fontFamily: "var(--font-serif)", fontSize: 17, fontWeight: 500, margin: "0 0 10px", letterSpacing: "-0.01em" }}>
            {cluster.label ?? "Tanpa label"}
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {[
              { lab: "Velocity", val: cluster.trend_velocity?.toFixed(1) ?? "—" },
              { lab: "Novelty", val: cluster.novelty_score != null ? Math.round(cluster.novelty_score * 100) + "%" : "—" },
              { lab: "Coverage", val: cluster.coverage_score != null ? Math.round(cluster.coverage_score * 100) + "%" : "—" },
              { lab: "Artikel", val: cluster.member_count != null ? String(cluster.member_count) : "—" },
            ].map(({ lab, val }) => (
              <div key={lab} className="score-chip">
                <span className="lab">{lab}</span>
                <span className="v">{val}</span>
              </div>
            ))}
          </div>
        </div>

        {cluster.summary && (
          <div style={{ padding: "10px 12px", background: "var(--bg-sunken)", borderRadius: "var(--radius)", borderLeft: "3px solid var(--accent)" }}>
            <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--accent-fg)", fontWeight: 600, marginBottom: 4 }}>
              AI Summary
            </div>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "var(--fg-muted)", fontFamily: "var(--font-serif)" }}>
              {cluster.summary}
            </p>
          </div>
        )}

        <div style={{ borderTop: "1px solid var(--line)", paddingTop: 10, display: "flex", gap: 16 }}>
          <span className="faint mono" style={{ fontSize: 11 }}>
            run: <span style={{ color: "var(--fg)" }}>{run?.algorithm ?? "—"} {run?.algorithm_version ?? ""}</span>
          </span>
          <span className="faint mono" style={{ fontSize: 11 }}>
            scored: <span style={{ color: "var(--fg)" }}>{cluster.insight_calculated_at ? fmtTime(cluster.insight_calculated_at) : "—"}</span>
          </span>
          {cluster.is_current && (
            <Link to={`/clusters/${cluster.id}`} className="btn btn-ghost" style={{ fontSize: 11, padding: "1px 8px", marginLeft: "auto" }}>
              Detail →
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Page ─────────────────────────────────────────────────────────── */

export function ClusteringRoute() {
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data: run } = useLatestClusterRun()
  const { data: clusters = [] } = useCurrentClusters("desc")

  const effectiveId = selectedId ?? clusters[0]?.id ?? null
  const selectedCluster = clusters.find(c => c.id === effectiveId)

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Topic <span className="serif">Clustering</span></h1>
          <p className="page-sub">
            Hasil clustering run terbaru — {clusters.filter(c => c.is_current).length} kluster aktif
          </p>
        </div>
        <div className="page-actions">
          <span className="faint mono" style={{ fontSize: 11.5 }}>
            {run ? `Run ${run.id.slice(0, 8)} · ${duration(run.started_at, run.finished_at)}` : "—"}
          </span>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 280px",
          gap: 20,
          padding: "20px 28px 48px",
          alignItems: "start",
        }}
      >
        {/* Left: run info + cluster list + insight panel */}
        <div>
          <RunInfoCard run={run} />
          <ArticleClustersCard
            selected={effectiveId}
            onSelect={(id) => navigate(`/clusters/${id}`)}
          />
          {selectedCluster && <ClusterInsightPanel cluster={selectedCluster} run={run} />}
        </div>

        {/* Right: trend signals */}
        <TrendSignalCard sticky />
      </div>
    </>
  )
}
