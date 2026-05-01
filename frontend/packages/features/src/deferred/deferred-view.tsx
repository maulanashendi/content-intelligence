import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { useDeferredClusters, clusterKeys } from "@ei-fe/api"
import { LoadingState, ErrorState, EmptyState } from "@ei-fe/ui"
import { DeferredTable } from "./deferred-table.js"

export function DeferredView() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error, isFetching } = useDeferredClusters()

  if (isLoading) return <LoadingState variant="table" />
  if (isError) {
    return (
      <ErrorState
        error={error}
        onRetry={() => queryClient.invalidateQueries({ queryKey: clusterKeys.deferred() })}
      />
    )
  }
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="Tidak ada topik ditunda"
        description="Semua topik saat ini direkomendasikan untuk ditulis."
      />
    )
  }

  return (
    <div style={{ opacity: isFetching ? 0.7 : 1, transition: "opacity 0.2s" }}>
      <DeferredTable clusters={data} onRowClick={(id) => navigate(`/clusters/${id}`)} />
    </div>
  )
}
