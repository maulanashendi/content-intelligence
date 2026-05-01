import type { ArticleMember } from "@ei-fe/api"
import { EmptyState } from "@ei-fe/ui"
import { ArticleRow } from "./article-row.js"

interface ArticleListProps {
  members: ArticleMember[]
}

export function ArticleList({ members }: ArticleListProps) {
  if (members.length === 0) {
    return <EmptyState title="Belum ada artikel anggota" />
  }
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Artikel Anggota</span>
        <span className="card-meta">{members.length} artikel</span>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Judul</th>
            <th>Sumber</th>
            <th>Tanggal</th>
            <th className="right">Relevansi</th>
          </tr>
        </thead>
        <tbody>
          {members.map((a) => (
            <ArticleRow key={a.id} article={a} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
