import { useState } from "react"
import { useCurrentClusters, useLatestClusterRun } from "@ei-fe/api"
import { ClusterTable } from "@ei-fe/ui"

interface ArticleClustersCardProps {
  onSelect: (id: string) => void
  selected?: string | null
}

export function ArticleClustersCard({ onSelect, selected }: ArticleClustersCardProps) {
  const [order, setOrder] = useState<"asc" | "desc">("desc")
  const { data: clusters = [] } = useCurrentClusters(order)
  const { data: run } = useLatestClusterRun()

  return (
    <ClusterTable
      clusters={clusters}
      onSelect={onSelect}
      selected={selected}
      runAlgorithm={run?.algorithm}
      order={order}
      onToggleOrder={() => setOrder(o => o === "desc" ? "asc" : "desc")}
    />
  )
}
