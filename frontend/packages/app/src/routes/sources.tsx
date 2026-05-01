import { Link } from "react-router-dom"

const SOURCES = [
  { id: 1, name: "Kompas RSS", type: "rss", url: "https://rss.kompas.com/nasional", lastFetch: "30 Apr 2025 · 06:12", articles: 142, status: "ok" },
  { id: 2, name: "CNN Indonesia", type: "rss", url: "https://rss.cnnindonesia.com/nasional", lastFetch: "30 Apr 2025 · 06:11", articles: 98, status: "ok" },
  { id: 3, name: "Detik Finance", type: "rss", url: "https://feed.detik.com/detikrss/d/finance", lastFetch: "30 Apr 2025 · 06:13", articles: 77, status: "ok" },
  { id: 4, name: "Bisnis Indonesia", type: "api", url: "https://api.bisnis.com/v2/articles", lastFetch: "30 Apr 2025 · 06:10", articles: 55, status: "ok" },
  { id: 5, name: "Republika", type: "rss", url: "https://www.republika.co.id/rss", lastFetch: "30 Apr 2025 · 05:48", articles: 33, status: "warn" },
  { id: 6, name: "Tempo Sitemap", type: "sitemap", url: "https://www.tempo.co/sitemap.xml", lastFetch: "30 Apr 2025 · 06:14", articles: 210, status: "ok" },
  { id: 7, name: "Antara News API", type: "api", url: "https://api.antaranews.com/news/v2", lastFetch: "29 Apr 2025 · 22:00", articles: 0, status: "bad" },
]

const STATUS_DOT: Record<string, string> = {
  ok: "dot-ok",
  warn: "dot-warn",
  bad: "dot-bad",
}

const TYPE_BADGE: Record<string, string> = {
  rss: "badge badge-active",
  api: "badge badge-recommended",
  sitemap: "badge badge-watching",
}

const TYPE_LABEL: Record<string, string> = {
  rss: "rss",
  api: "api",
  sitemap: "sitemap",
}

export function SourcesRoute() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Content <span className="serif">Sources</span></h1>
          <p className="page-sub">Sumber konten yang diingest pipeline setiap hari</p>
        </div>
        <div className="page-actions">
          <Link to="/sources/rss" className="btn">+ RSS Feed</Link>
        </div>
      </div>

      <div className="page-body">
        <div className="grid grid-4" style={{ marginBottom: 20 }}>
          <div className="kpi">
            <div className="kpi-label">Total Sumber</div>
            <div className="kpi-value">{SOURCES.length}</div>
          </div>
          <div className="kpi">
            <div className="kpi-label">Aktif</div>
            <div className="kpi-value">{SOURCES.filter(s => s.status === "ok").length}</div>
          </div>
          <div className="kpi">
            <div className="kpi-label">Bermasalah</div>
            <div className="kpi-value" style={{ color: "var(--bad)" }}>
              {SOURCES.filter(s => s.status !== "ok").length}
            </div>
          </div>
          <div className="kpi">
            <div className="kpi-label">Total Artikel</div>
            <div className="kpi-value">{SOURCES.reduce((s, r) => s + r.articles, 0).toLocaleString("id-ID")}</div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <span className="card-title">Semua sumber</span>
            <span className="card-meta">{SOURCES.length} terdaftar</span>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Nama</th>
                <th>Tipe</th>
                <th>URL</th>
                <th>Terakhir fetch</th>
                <th className="right">Artikel</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {SOURCES.map((s) => (
                <tr key={s.id} className="row-clickable">
                  <td style={{ fontWeight: 500 }}>{s.name}</td>
                  <td><span className={TYPE_BADGE[s.type]}>{TYPE_LABEL[s.type]}</span></td>
                  <td className="mono faint" style={{ fontSize: 11.5, maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.url}</td>
                  <td className="mono faint" style={{ fontSize: 11.5 }}>{s.lastFetch}</td>
                  <td className="num right">{s.articles}</td>
                  <td>
                    <span className="dot-status" style={{ display: "inline-block", marginRight: 6 }}>
                      <span className={`dot-status ${STATUS_DOT[s.status]}`} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
