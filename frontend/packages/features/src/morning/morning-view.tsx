import { useNavigate, useSearchParams } from "react-router-dom"
import { useMemo } from "react"
import { useQueryClient, useQueries } from "@tanstack/react-query"
import { useMorningClusters, useLatestClusterRun, clusterKeys, clusterDetailQueryOptions } from "@ei-fe/api"
import type { ClusterDetail } from "@ei-fe/api"
import { Kpi, LoadingState, ErrorState } from "@ei-fe/ui"
import { ArticleClustersCard } from "./article-clusters-card.js"
import { ClusterForceGraph } from "./cluster-force-graph.js"
import { EditorialBriefing } from "./editorial-briefing.js"
import { NewsVolumeTrendCard } from "./news-volume-trend-card.js"
import { ClusterBentoCard } from "./cluster-bento-card.js"
import { OpportunityMatrixCard } from "./opportunity-matrix-card.js"
import { TrendSignalCard } from "./trend-signal-card.js"
import { parseDnaParam } from "./dna-param.js"
import { DnaToggle } from "./dna-toggle.js"

function KpiRow({ clusters }: { clusters: { tempo_covered: boolean | null; underperformed: boolean | null; member_count: number | null; trend_velocity: number | null }[] }) {
  const uncovered = clusters.filter((c) => !c.tempo_covered).length
  const underperformed = clusters.filter((c) => c.underperformed).length
  const totalArticles = clusters.reduce((sum, c) => sum + (c.member_count ?? 0), 0)
  const avgVelocity =
    clusters.length > 0
      ? clusters.reduce((sum, c) => sum + (c.trend_velocity ?? 0), 0) / clusters.length
      : 0

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, padding: "20px 28px 0" }}>
      <Kpi label="Belum Ditulis" value={uncovered} />
      <Kpi label="Underperformed" value={underperformed} />
      <Kpi label="Total Artikel" value={totalArticles.toLocaleString("id-ID")} />
      <Kpi label="Avg Velocity" value={avgVelocity.toFixed(2)} />
    </div>
  )
}

function fmtRunTime(iso: string): string {
  const d = /Z|[+-]\d{2}:?\d{2}$/.test(iso) ? new Date(iso) : new Date(iso + "Z")
  return d.toLocaleString("id-ID", {
    day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }) + " WIB"
}

export function MorningView() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const dnaOn = parseDnaParam(params)

  const setDna = (next: boolean) => {
    setParams(prev => {
      const p = new URLSearchParams(prev)
      if (next) p.delete("dna"); else p.set("dna", "off")
      return p
    }, { replace: true })
  }

  const { data, isLoading, isError, error, isFetching } = useMorningClusters(dnaOn)
  const { data: run } = useLatestClusterRun()

  const detailQueries = useQueries({
    queries: (data?.clusters ?? []).map((c) => clusterDetailQueryOptions(c.id)),
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
        onRetry={() => queryClient.invalidateQueries({ queryKey: clusterKeys.morning(dnaOn) })}
      />
    )
  }

  const clusters = data?.clusters ?? []

  if (clusters.length === 0) {
    return (
      <div style={{ padding: "60px 28px", textAlign: "center" }}>
        <p style={{ color: "var(--fg-muted)", fontSize: 14, margin: 0 }}>
          Belum ada topik — pipeline sedang berjalan atau scoring belum selesai.
        </p>
        <p style={{ color: "var(--fg-faint)", fontSize: 12, marginTop: 6 }}>
          Halaman ini akan terisi setelah cluster run harian (06:00 WIB) selesai.
        </p>
      </div>
    )
  }

  return (
    <div style={{ opacity: isFetching ? 0.7 : 1, transition: "opacity 0.2s" }}>
      {run && !run.has_insights && (
        <div style={{
          margin: "16px 28px 0",
          padding: "8px 14px",
          background: "var(--bg-sunken)",
          borderLeft: "3px solid var(--fg-faint)",
          borderRadius: "var(--radius)",
          fontSize: 12.5,
          color: "var(--fg-muted)",
        }}>
          Menampilkan data dari run sebelumnya — run {fmtRunTime(run.started_at)} sedang diproses (clustering atau scoring belum selesai).
        </div>
      )}
      <KpiRow clusters={clusters} />

      <div style={{ padding: "16px 28px 0", display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 12, color: "var(--fg-faint)" }}>
          Hanya tema Tempo (desk + kebutuhan pembaca)
        </span>
        <DnaToggle on={dnaOn} onChange={setDna} />
      </div>

      <div style={{ padding: "12px 28px 0" }}>
        <OpportunityMatrixCard clusters={clusters} dnaOn={dnaOn} />
      </div>

      <div style={{ padding: "20px 28px 0" }}>
        <NewsVolumeTrendCard />
      </div>

      <div style={{ padding: "20px 28px 0" }}>
        <ClusterBentoCard dnaOn={dnaOn} />
      </div>

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
          <ArticleClustersCard
            clusters={clusters}
            runAlgorithm={run?.algorithm}
            onSelect={(id) => navigate(`/clusters/${id}`)}
          />
        </div>
        <TrendSignalCard />
      </div>
    </div>
  )
}
