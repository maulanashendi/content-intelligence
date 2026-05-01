import { useQueryClient } from "@tanstack/react-query"
import { articleKeys } from "@ei-fe/api"
import { PageHead, RefreshCw } from "@ei-fe/ui"
import { ArticleView } from "@ei-fe/features"

export function ArticleRoute() {
  const queryClient = useQueryClient()
  return (
    <>
      <PageHead
        title="Artikel"
        subtitle="Semua artikel yang telah diingest, terbaru lebih dulu"
        action={
          <button
            className="btn btn-ghost"
            onClick={() => queryClient.invalidateQueries({ queryKey: articleKeys.all })}
          >
            <RefreshCw className="icon" style={{ width: 13, height: 13 }} />
            Refresh
          </button>
        }
      />
      <ArticleView />
    </>
  )
}
