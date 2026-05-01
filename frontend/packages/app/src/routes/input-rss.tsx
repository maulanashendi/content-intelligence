import { useState } from "react"
import { Link } from "react-router-dom"

const PREVIEW_ARTICLES = [
  { title: "Pertamina Naikkan Harga BBM Non-Subsidi per 1 Mei 2025", published: "30 Apr 2025 · 08:14", source: "kompas.com" },
  { title: "Pemerintah Kaji Dampak Kenaikan BBM terhadap Inflasi", published: "30 Apr 2025 · 07:50", source: "kompas.com" },
  { title: "DPR Minta Pemerintah Jelaskan Alasan Kenaikan BBM", published: "30 Apr 2025 · 07:22", source: "kompas.com" },
]

type Status = "idle" | "loading" | "ok" | "error"

export function InputRssRoute() {
  const [url, setUrl] = useState("")
  const [name, setName] = useState("")
  const [interval, setInterval] = useState("6h")
  const [previewStatus, setPreviewStatus] = useState<Status>("idle")
  const [saveStatus, setSaveStatus] = useState<Status>("idle")

  function handlePreview(e: React.FormEvent) {
    e.preventDefault()
    if (!url) return
    setPreviewStatus("loading")
    setTimeout(() => setPreviewStatus("ok"), 1200)
  }

  function handleSave() {
    setSaveStatus("loading")
    setTimeout(() => setSaveStatus("ok"), 900)
  }

  return (
    <>
      <div className="page-head">
        <div>
          <Link to="/sources" className="btn btn-ghost" style={{ fontSize: 12, padding: "3px 8px", marginBottom: 12, display: "inline-flex" }}>
            ← Content Sources
          </Link>
          <h1 className="page-title">Input <span className="serif">RSS Feed</span></h1>
          <p className="page-sub">Tambahkan sumber RSS baru ke pipeline ingest</p>
        </div>
      </div>

      <div className="page-body" style={{ maxWidth: 680 }}>
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <span className="card-title">Konfigurasi Feed</span>
          </div>
          <form onSubmit={handlePreview} style={{ padding: "16px 18px", display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--fg-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                RSS URL *
              </label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://rss.kompas.com/nasional"
                required
                style={inputStyle}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--fg-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Nama Sumber
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Kompas Nasional"
                style={inputStyle}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--fg-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Interval Fetch
              </label>
              <select value={interval} onChange={(e) => setInterval(e.target.value)} style={inputStyle}>
                <option value="1h">Setiap 1 jam</option>
                <option value="3h">Setiap 3 jam</option>
                <option value="6h">Setiap 6 jam</option>
                <option value="12h">Setiap 12 jam</option>
                <option value="24h">Setiap 24 jam</option>
              </select>
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn" disabled={previewStatus === "loading"}>
                {previewStatus === "loading" ? "Mengambil…" : "Preview Feed"}
              </button>
              {previewStatus === "ok" && (
                <button
                  type="button"
                  className="btn"
                  style={{ background: "var(--fg)", color: "var(--bg-elev)", borderColor: "var(--fg)" }}
                  onClick={handleSave}
                  disabled={saveStatus === "loading"}
                >
                  {saveStatus === "ok" ? "✓ Tersimpan" : saveStatus === "loading" ? "Menyimpan…" : "Simpan Sumber"}
                </button>
              )}
            </div>
          </form>
        </div>

        {previewStatus === "ok" && (
          <div className="card">
            <div className="card-head">
              <span className="card-title">Preview Artikel</span>
              <span className="card-meta">3 artikel terbaru</span>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Judul</th>
                  <th>Sumber</th>
                  <th>Tanggal</th>
                </tr>
              </thead>
              <tbody>
                {PREVIEW_ARTICLES.map((a, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{a.title}</td>
                    <td className="mono faint" style={{ fontSize: 11.5, whiteSpace: "nowrap" }}>{a.source}</td>
                    <td className="mono faint" style={{ fontSize: 11.5, whiteSpace: "nowrap" }}>{a.published}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {saveStatus === "ok" && (
          <div style={{ marginTop: 16, padding: "12px 16px", borderRadius: "var(--radius)", background: "var(--ok-soft)", color: "oklch(0.42 0.13 155)", fontSize: 13, fontWeight: 500 }}>
            ✓ RSS feed berhasil ditambahkan dan akan diingest pada run berikutnya.
          </div>
        )}
      </div>
    </>
  )
}

const inputStyle: React.CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: 13,
  padding: "7px 10px",
  border: "1px solid var(--line-strong)",
  borderRadius: "var(--radius)",
  background: "var(--bg-elev)",
  color: "var(--fg)",
  outline: "none",
  width: "100%",
}
