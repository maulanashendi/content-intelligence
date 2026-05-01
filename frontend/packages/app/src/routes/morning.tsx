import { useQueryClient } from "@tanstack/react-query"
import { clusterKeys } from "@ei-fe/api"
import { PageHead, RefreshCw } from "@ei-fe/ui"
import { MorningView } from "@ei-fe/features"

export function MorningRoute() {
  const queryClient = useQueryClient()
  return (
    <>
      <PageHead
        title="Morning"
        titleDecorator="Brief"
        subtitle="Topik disarankan untuk ditulis hari ini"
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
      <MorningView />
    </>
  )
}
