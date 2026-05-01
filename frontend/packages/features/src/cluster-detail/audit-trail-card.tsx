import type { ClusterDetail } from "@ei-fe/api"

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
    if (!iso) return "—"
    return new Date(iso).toLocaleString("id-ID", {
      day: "numeric", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
      timeZone: "Asia/Jakarta",
    }) + " WIB"
  }

  const noveltyPct = cluster.novelty_score != null ? Math.round(cluster.novelty_score * 100) : null
  const coveragePct = cluster.coverage_score != null ? Math.round(cluster.coverage_score * 100) : null

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
      label: "Skor pipeline dihitung",
      detail: (
        <>
          velocity <span className="highlight">{cluster.trend_velocity?.toFixed(1) ?? "—"}</span>
          {" · "}novelty <span className="highlight">{noveltyPct != null ? noveltyPct + "%" : "—"}</span>
          {" · "}coverage <span className="highlight">{coveragePct != null ? coveragePct + "%" : "—"}</span>
          {coveragePct != null && coveragePct < 40 && (
            <><br /><span style={{ color: "var(--ok)" }}>✓ coverage rendah — lane terbuka</span></>
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
      step: "07 · rekomendasi",
      label: "Masuk Morning Brief",
      detail: (
        <>
          rekomendasi: <span className="highlight">{cluster.recommendation ?? "—"}</span>
          <br />siap untuk ditulis oleh redaksi
        </>
      ),
      dot: "active",
      tag: {
        label: cluster.recommendation === "trending" ? "recommended" : cluster.recommendation === "worth_writing" ? "worth writing" : "saturated",
        bg: cluster.recommendation === "trending" ? "var(--accent-soft)" : cluster.recommendation === "worth_writing" ? "var(--info-soft)" : "var(--warn-soft)",
        color: cluster.recommendation === "trending" ? "var(--accent-fg)" : cluster.recommendation === "worth_writing" ? "oklch(0.42 0.13 230)" : "oklch(0.45 0.13 75)",
      },
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
