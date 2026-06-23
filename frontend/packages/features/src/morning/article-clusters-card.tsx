import { useState } from "react"
import { useCurrentClusters, useLatestClusterRun, type ClusterSummary } from "@ei-fe/api"
import { ClusterTable } from "@ei-fe/ui"

interface ArticleClustersCardProps {
  onSelect: (id: string) => void
  selected?: string | null
  clusters?: ClusterSummary[]
  runAlgorithm?: string | null
}

export function ArticleClustersCard({
  onSelect,
  selected,
  clusters: providedClusters,
  runAlgorithm,
}: ArticleClustersCardProps) {
  const [order, setOrder] = useState<"asc" | "desc">("desc")
  const shouldFetchCurrent = providedClusters == null
  const { data: _listData } = useCurrentClusters(order, shouldFetchCurrent)
  const clusters = providedClusters ?? _listData?.clusters ?? []
  const { data: run } = useLatestClusterRun()

  return (
    <ClusterTable
      clusters={clusters}
      onSelect={onSelect}
      selected={selected}
      runAlgorithm={runAlgorithm ?? run?.algorithm}
      order={shouldFetchCurrent ? order : undefined}
      onToggleOrder={shouldFetchCurrent ? () => setOrder(o => o === "desc" ? "asc" : "desc") : undefined}
    />
  )
}
