import type { ArticleMember } from "@ei-fe/api"
import { formatDate } from "@ei-fe/core"

interface FirstReportCardProps {
  members: ArticleMember[]
  clusterLabel: string | null
}

export function FirstReportCard({ members, clusterLabel }: FirstReportCardProps) {
  const sorted = [...members].sort((a, b) => {
    if (!a.published_at) return 1
    if (!b.published_at) return -1
    return new Date(a.published_at).getTime() - new Date(b.published_at).getTime()
  })
  const first = sorted[0]
  if (!first) return null

  const totalSources = new Set(members.map((m) => m.source_name)).size
  const daysSince = first.published_at
    ? Math.floor((Date.now() - new Date(first.published_at).getTime()) / 86400000)
    : null

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">First Report</span>
        <span className="card-meta">who broke the story</span>
      </div>
      <div className="first-report-body">
        <div className="first-report-meta">
          <span className="badge badge-watching" style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
            {first.source_name}
          </span>
          <span className="faint mono" style={{ fontSize: 11 }}>
            {formatDate(first.published_at)}
            {daysSince !== null && daysSince > 0 && ` · ${daysSince}h lalu`}
          </span>
          {first.relevance_score != null && (
            <span className="faint mono" style={{ fontSize: 11 }}>
              rel {Math.round(first.relevance_score * 100)}%
            </span>
          )}
        </div>
        <a
          href={first.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ textDecoration: "none" }}
        >
          <p className="first-report-headline">{first.title}</p>
        </a>
        {first.first_paragraph && (
          <p className="first-report-excerpt">{first.first_paragraph}</p>
        )}
        <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--line)", display: "flex", gap: 16 }}>
          <span className="faint mono" style={{ fontSize: 11 }}>
            <strong style={{ color: "var(--fg)" }}>{members.length}</strong> artikel total
          </span>
          <span className="faint mono" style={{ fontSize: 11 }}>
            <strong style={{ color: "var(--fg)" }}>{totalSources}</strong> sumber berbeda
          </span>
          {clusterLabel && sorted[1] && (
            <span className="faint mono" style={{ fontSize: 11 }}>
              follow-up: <strong style={{ color: "var(--fg)" }}>{sorted[1].source_name}</strong>
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
