import type { ClusterDetail } from "@ei-fe/api"
import { formatDateTime } from "@ei-fe/core"

interface AuditTrailCardProps {
  cluster: ClusterDetail
}

type DotKind = "done" | "active" | "warn" | "muted"

interface AuditEvent {
  step: string
  label: string
  detail: React.ReactNode
  dot: DotKind
  tag?: { label: string; bg: string; color: string }
}

import * as React from "react"

function buildTrail(cluster: ClusterDetail): AuditEvent[] {
  const members = [...cluster.members].sort((a, b) => {
    if (!a.published_at) return 1
    if (!b.published_at) return -1
    return new Date(a.published_at).getTime() - new Date(b.published_at).getTime()
  })

  const first = members[0]
  const last = members[members.length - 1]
  const sources = new Set(members.map((m) => m.source_name))

  function fmtTime(iso: string | null | undefined): string {
    return iso ? formatDateTime(iso) + " WIB" : "—"
  }

  return [
    {
      step: "01 · ingest",
      label: "Artikel pertama terdeteksi",
      detail: (
        <>
          <span className="highlight">{first?.source_name ?? "—"}</span>
          {" · "}{fmtTime(first?.published_at)}
          <br />"{first?.title?.slice(0, 72) ?? "—"}…"
        </>
      ),
      dot: "done",
    },
    {
      step: "02 · embedding",
      label: "Artikel divektorisasi",
      detail: (
        <>
          <span className="highlight">{members.length} artikel</span> · model gemma-embedding-300m
          <br />768-dim vectors · batch size 32
        </>
      ),
      dot: "done",
    },
    {
      step: "03 · clustering",
      label: "Kluster dibentuk",
      detail: (
        <>
          UMAP → HDBSCAN · <span className="highlight">{sources.size} sumber</span>
          <br />{cluster.member_count ?? members.length} artikel · min_cluster_size 5
        </>
      ),
      dot: "done",
    },
    {
      step: "04 · labeling",
      label: "Label dihasilkan AI",
      detail: (
        <>
          "<span className="highlight">{cluster.label ?? "Tanpa label"}</span>"
          <br />Gemma 2B 4-bit · temp 0.3
        </>
      ),
      dot: "done",
      tag: { label: "AI", bg: "var(--accent-soft)", color: "var(--accent-fg)" },
    },
    {
      step: "05 · scoring",
      label: "Sinyal dihitung",
      detail: (
        <>
          velocity <span className="highlight">{cluster.trend_velocity?.toFixed(2) ?? "—"}</span>
          {" · "}kompetitor <span className="highlight">{cluster.competitor_count ?? "—"}</span>
          {" · "}trend match <span className="highlight">{cluster.trend_match_count ?? "—"}</span>
          {cluster.underperformed && (
            <><br /><span style={{ color: "var(--warn)" }}>⚠ artikel underperformed di GSC</span></>
          )}
          {!cluster.tempo_covered && (
            <><br /><span style={{ color: "var(--ok)" }}>✓ Tempo belum menulis — lane terbuka</span></>
          )}
        </>
      ),
      dot: "done",
    },
    {
      step: "06 · ingest lanjutan",
      label: "Artikel terakhir masuk",
      detail: (
        <>
          <span className="highlight">{last?.source_name ?? "—"}</span>
          {" · "}{fmtTime(last?.published_at)}
          <br />total {members.length} artikel · {sources.size} outlet berbeda
        </>
      ),
      dot: "done",
    },
    {
      step: "07 · status",
      label: "Status Tempo",
      detail: (
        <>
          tempo_covered: <span className="highlight">{cluster.tempo_covered ? "ya" : "belum"}</span>
          {cluster.last_internal_days_ago != null && (
            <><br />terakhir ditulis <span className="highlight">{cluster.last_internal_days_ago} hari lalu</span></>
          )}
          <br />siap untuk editorial review
        </>
      ),
      dot: "active",
      tag: cluster.tempo_covered
        ? { label: "sudah ditulis", bg: "var(--ok-soft)", color: "var(--ok-fg)" }
        : { label: "belum ditulis", bg: "var(--accent-soft)", color: "var(--accent-fg)" },
    },
  ]
}

export function AuditTrailCard({ cluster }: AuditTrailCardProps) {
  const trail = buildTrail(cluster)

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Audit Trail</span>
        <span className="card-meta">pipeline · {trail.length} langkah</span>
      </div>
      <div className="audit-list">
        {trail.map((event, i) => (
          <div key={i} className="audit-item">
            <div className="audit-dot-wrap">
              <div className={`audit-dot ${event.dot}`} />
            </div>
            <div className="audit-content">
              <div className="audit-step">{event.step}</div>
              <div className="audit-label">{event.label}</div>
              <div className="audit-detail">{event.detail}</div>
              {event.tag && (
                <span
                  className="audit-tag"
                  style={{ background: event.tag.bg, color: event.tag.color }}
                >
                  {event.tag.label}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
