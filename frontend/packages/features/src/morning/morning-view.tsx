import { useNavigate } from "react-router-dom"
import { useMemo } from "react"
import { useQueryClient, useQueries } from "@tanstack/react-query"
import { useMorningClusters, clusterKeys, clusterDetailQueryOptions } from "@ei-fe/api"
import type { ClusterDetail } from "@ei-fe/api"
import { LoadingState, ErrorState } from "@ei-fe/ui"
import { ArticleClustersCard } from "./article-clusters-card.js"
import { ClusterForceGraph } from "./cluster-force-graph.js"
import { EditorialBriefing } from "./editorial-briefing.js"
import { TrendSignalCard } from "./trend-signal-card.js"

function KpiRow({ clusters }: { clusters: { recommendation: string | null; member_count: number | null; trend_velocity: number | null }[] }) {
  const trending = clusters.filter((c) => c.recommendation === "trending").length
  const worthWriting = clusters.filter((c) => c.recommendation === "worth_writing").length
  const totalArticles = clusters.reduce((sum, c) => sum + (c.member_count ?? 0), 0)
  const avgVelocity =
    clusters.length > 0
      ? clusters.reduce((sum, c) => sum + (c.trend_velocity ?? 0), 0) / clusters.length
      : 0

  return (
    <div className="grid grid-4" style={{ padding: "20px 28px 0" }}>
      <div className="kpi">
        <div className="kpi-label">Trending</div>
        <div className="kpi-value">{trending}</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Worth Writing</div>
        <div className="kpi-value">{worthWriting}</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Total Artikel</div>
        <div className="kpi-value">{totalArticles.toLocaleString("id-ID")}</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Avg Velocity</div>
        <div className="kpi-value">{avgVelocity.toFixed(1)}</div>
      </div>
    </div>
  )
}

export function MorningView() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error, isFetching } = useMorningClusters()

  const detailQueries = useQueries({
    queries: (data ?? []).map((c) => clusterDetailQueryOptions(c.id)),
  })

  const loadedDetails = useMemo(
    () =>
      detailQueries
        .map((q) => (q as { data: ClusterDetail | undefined }).data)
        .filter((d): d is ClusterDetail => d != null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [detailQueries.map((q) => (q as { data: ClusterDetail | undefined }).data?.id).join(",")],
  )

  if (isLoading) return <LoadingState variant="table" />
  if (isError) {
    return (
      <ErrorState
        error={error}
        onRetry={() => queryClient.invalidateQueries({ queryKey: clusterKeys.morning() })}
      />
    )
  }

  const clusters = data ?? []

  return (
    <div style={{ opacity: isFetching ? 0.7 : 1, transition: "opacity 0.2s" }}>
      <KpiRow clusters={clusters} />

      <div style={{ padding: "20px 28px 0" }}>
        <ClusterForceGraph
          details={loadedDetails}
          onClusterClick={(id) => navigate(`/clusters/${id}`)}
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 300px",
          gap: 20,
          padding: "20px 28px 40px",
          alignItems: "start",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <EditorialBriefing clusters={clusters} />
          <ArticleClustersCard onSelect={(id) => navigate(`/clusters/${id}`)} />
        </div>
        <TrendSignalCard />
      </div>
    </div>
  )
}
