import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useArticles, articleKeys } from "@ei-fe/api"
import { LoadingState, ErrorState, EmptyState } from "@ei-fe/ui"
import { ArticleTable } from "./article-table.js"

const PAGE_SIZE = 20

export function ArticleView() {
  const [page, setPage] = useState(1)
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error, isFetching } = useArticles(page, PAGE_SIZE)

  if (isLoading) return <LoadingState variant="table" />
  if (isError) {
    return (
      <ErrorState
        error={error}
        onRetry={() => queryClient.invalidateQueries({ queryKey: articleKeys.all })}
      />
    )
  }
  if (!data || data.total === 0) {
    return (
      <EmptyState
        title="Belum ada artikel"
        description="Pipeline ingest belum berjalan atau belum ada artikel yang berhasil diambil."
      />
    )
  }

  return (
    <div style={{ opacity: isFetching ? 0.7 : 1, transition: "opacity 0.2s" }}>
      <ArticleTable articles={data.items} />
      <Pagination
        page={data.page}
        totalPages={data.total_pages}
        total={data.total}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => Math.min(data.total_pages, p + 1))}
      />
    </div>
  )
}

interface PaginationProps {
  page: number
  totalPages: number
  total: number
  onPrev: () => void
  onNext: () => void
}

function Pagination({ page, totalPages, total, onPrev, onNext }: PaginationProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 28px 24px",
        fontSize: 12.5,
      }}
    >
      <span className="faint">
        {total.toLocaleString("id-ID")} artikel · halaman {page} dari {totalPages}
      </span>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn btn-ghost" onClick={onPrev} disabled={page <= 1}>
          ← Sebelumnya
        </button>
        <button className="btn btn-ghost" onClick={onNext} disabled={page >= totalPages}>
          Berikutnya →
        </button>
      </div>
    </div>
  )
}
