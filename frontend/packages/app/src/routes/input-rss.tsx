import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useCreateSource } from "@ei-fe/api"
import { toUserMessage } from "@ei-fe/core"

const PREVIEW_ARTICLES = [
  { title: "Pertamina Naikkan Harga BBM Non-Subsidi per 1 Mei 2025", published: "30 Apr 2025 · 08:14", source: "kompas.com" },
  { title: "Pemerintah Kaji Dampak Kenaikan BBM terhadap Inflasi", published: "30 Apr 2025 · 07:50", source: "kompas.com" },
  { title: "DPR Minta Pemerintah Jelaskan Alasan Kenaikan BBM", published: "30 Apr 2025 · 07:22", source: "kompas.com" },
]

const URL_RE = /^https?:\/\/.+/i

export function InputRssRoute() {
  const navigate = useNavigate()
  const createSource = useCreateSource()
  const [url, setUrl] = useState("")
  const [name, setName] = useState("")
  const [isEnabled, setIsEnabled] = useState(true)
  const [urlError, setUrlError] = useState("")
  const [previewShown, setPreviewShown] = useState(false)

  function validateUrl(value: string): boolean {
    if (!value) { setUrlError("URL wajib diisi."); return false }
    if (!URL_RE.test(value)) { setUrlError("URL harus diawali http:// atau https://"); return false }
    setUrlError("")
    return true
  }

  function handlePreview(e: React.FormEvent) {
    e.preventDefault()
    if (!validateUrl(url)) return
    setPreviewShown(true)
  }

  async function handleSave() {
    if (!validateUrl(url)) return
    await createSource.mutateAsync(
      { url, name: name.trim().slice(0, 200), is_enabled: isEnabled },
      { onSuccess: () => navigate("/sources") },
    )
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
              <label style={labelStyle}>RSS URL *</label>
              <input
                type="url"
                value={url}
                onChange={(e) => { setUrl(e.target.value); if (urlError) validateUrl(e.target.value) }}
                placeholder="https://rss.kompas.com/nasional"
                required
                style={inputStyle}
              />
              {urlError && <span style={{ fontSize: 12, color: "var(--bad)" }}>{urlError}</span>}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={labelStyle}>Nama Sumber</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Kompas Nasional"
                maxLength={200}
                style={inputStyle}
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                id="is-enabled"
                type="checkbox"
                checked={isEnabled}
                onChange={(e) => setIsEnabled(e.target.checked)}
                style={{ width: 15, height: 15, cursor: "pointer", accentColor: "var(--accent)" }}
              />
              <label htmlFor="is-enabled" style={{ fontSize: 13, cursor: "pointer" }}>Aktifkan sumber saat disimpan</label>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button type="submit" className="btn">Preview Feed</button>
              {previewShown && (
                <button
                  type="button"
                  className="btn"
                  style={{ background: "var(--fg)", color: "var(--bg-elev)", borderColor: "var(--fg)" }}
                  onClick={handleSave}
                  disabled={createSource.isPending}
                >
                  {createSource.isPending ? "Menyimpan…" : "Simpan Sumber"}
                </button>
              )}
            </div>

            {createSource.isError && (
              <span style={{ fontSize: 12, color: "var(--bad)" }}>{toUserMessage(createSource.error)}</span>
            )}
          </form>
        </div>

        {previewShown && (
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
      </div>
    </>
  )
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  color: "var(--fg-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
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
