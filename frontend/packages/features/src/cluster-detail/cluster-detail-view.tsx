import { Link } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { useClusterDetail, clusterKeys } from "@ei-fe/api"
import { isApiError } from "@ei-fe/core"
import { LoadingState, ErrorState, EmptyState } from "@ei-fe/ui"
import { ClusterHeader } from "./cluster-header.js"
import { ArticleList } from "./article-list.js"
import { FirstReportCard } from "./first-report-card.js"
import { AuditTrailCard } from "./audit-trail-card.js"
import { GeneratedAnglesCard } from "./generated-angles-card.js"

interface ClusterDetailViewProps {
  id: string
}

export function ClusterDetailView({ id }: ClusterDetailViewProps) {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error } = useClusterDetail(id)

  if (isLoading) return <LoadingState variant="detail" />

  if (isError) {
    if (isApiError(error) && error.status === 404) {
      return (
        <EmptyState
          title="Cluster tidak ditemukan"
          description="Cluster ini tidak ada atau bukan dari run terbaru."
          action={
            <Link to="/morning" style={{ color: "var(--accent-fg)", fontSize: 13 }}>
              ← Kembali ke Morning Brief
            </Link>
          }
        />
      )
    }
    return (
      <ErrorState
        error={error}
        onRetry={() => queryClient.invalidateQueries({ queryKey: clusterKeys.detail(id) })}
      />
    )
  }

  if (!data) return null

  return (
    <div style={{ paddingBottom: 48 }}>
      <ClusterHeader cluster={data} />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 320px",
          gap: 20,
          padding: "20px 28px 0",
          alignItems: "start",
        }}
      >
        {/* Left: generated angles + article list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <GeneratedAnglesCard cluster={data} />
          <ArticleList members={data.members} />
        </div>

        {/* Right: first report + audit trail */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <FirstReportCard members={data.members} clusterLabel={data.label} />
          <AuditTrailCard cluster={data} />
        </div>
      </div>
    </div>
  )
}
