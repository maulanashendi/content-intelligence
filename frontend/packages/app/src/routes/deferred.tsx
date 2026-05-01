import { useQueryClient } from "@tanstack/react-query"
import { clusterKeys } from "@ei-fe/api"
import { PageHead, RefreshCw } from "@ei-fe/ui"
import { DeferredView } from "@ei-fe/features"

export function DeferredRoute() {
  const queryClient = useQueryClient()
  return (
    <>
      <PageHead
        title="Ditunda"
        subtitle="Topik jenuh — kompetitor sudah banyak menulis"
        action={
          <button
            className="btn btn-ghost"
            onClick={() => queryClient.invalidateQueries({ queryKey: clusterKeys.all })}
          >
            <RefreshCw className="icon" style={{ width: 13, height: 13 }} />
            Refresh
          </button>
        }
      />
      <DeferredView />
    </>
  )
}
