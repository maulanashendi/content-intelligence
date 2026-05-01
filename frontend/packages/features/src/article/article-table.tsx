import type { Article } from "@ei-fe/api"

interface ArticleTableProps {
  articles: Article[]
}

function SourceTypeBadge({ type }: { type: "rss" | "internal" }) {
  return (
    <span
      className={`badge ${type === "internal" ? "badge-watching" : "badge-active"}`}
      style={{ fontSize: 10.5 }}
    >
      {type === "internal" ? "internal" : "rss"}
    </span>
  )
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("id-ID", {
    timeZone: "Asia/Jakarta",
    day: "numeric",
    month: "short",
    year: "numeric",
  })
}

export function ArticleTable({ articles }: ArticleTableProps) {
  return (
    <div className="card" style={{ margin: "24px 28px" }}>
      <div className="card-head">
        <span className="card-title">Semua Artikel</span>
        <span className="card-meta">diurutkan berdasarkan waktu ingest terbaru</span>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: "45%" }}>Judul</th>
            <th>Sumber</th>
            <th>Tipe</th>
            <th>Terbit</th>
            <th>Diingest</th>
          </tr>
        </thead>
        <tbody>
          {articles.map((a) => (
            <tr key={a.id}>
              <td>
                <a
                  href={a.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="link"
                  style={{ fontFamily: "var(--font-serif)", fontSize: 14.5, fontWeight: 500, lineHeight: 1.3 }}
                >
                  {a.title}
                </a>
                {a.first_paragraph && (
                  <div className="faint" style={{ fontSize: 11.5, marginTop: 3, lineHeight: 1.4 }}>
                    {a.first_paragraph.slice(0, 120)}
                    {a.first_paragraph.length > 120 ? "…" : ""}
                  </div>
                )}
              </td>
              <td className="faint" style={{ fontSize: 12.5 }}>
                {a.source_name}
              </td>
              <td>
                <SourceTypeBadge type={a.source_type} />
              </td>
              <td className="faint mono" style={{ fontSize: 12 }}>
                {fmtDate(a.published_at)}
              </td>
              <td className="faint mono" style={{ fontSize: 12 }}>
                {fmtDate(a.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
