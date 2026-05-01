import { useState } from "react"
import { Link } from "react-router-dom"

type AuthType = "none" | "apikey" | "bearer"
type Status = "idle" | "loading" | "ok" | "error"

const PREVIEW_RESPONSE = {
  status: "ok",
  total: 48,
  articles: [
    { id: "art-001", title: "Antara: Kenaikan BBM Picu Demo Buruh", published_at: "2025-04-30T07:12:00Z", url: "https://antaranews.com/berita/001" },
    { id: "art-002", title: "Antara: Menko Airlangga Sebut Kenaikan Wajar", published_at: "2025-04-30T06:55:00Z", url: "https://antaranews.com/berita/002" },
  ],
}

export function InputApiRoute() {
  const [endpoint, setEndpoint] = useState("")
  const [authType, setAuthType] = useState<AuthType>("none")
  const [apiKey, setApiKey] = useState("")
  const [titlePath, setTitlePath] = useState("articles[].title")
  const [urlPath, setUrlPath] = useState("articles[].url")
  const [datePath, setDatePath] = useState("articles[].published_at")
  const [testStatus, setTestStatus] = useState<Status>("idle")
  const [saveStatus, setSaveStatus] = useState<Status>("idle")

  function handleTest(e: React.FormEvent) {
    e.preventDefault()
    if (!endpoint) return
    setTestStatus("loading")
    setTimeout(() => setTestStatus("ok"), 1400)
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
          <h1 className="page-title">Input <span className="serif">API Source</span></h1>
          <p className="page-sub">Tambahkan sumber konten via REST API dengan mapping field</p>
        </div>
      </div>

      <div className="page-body" style={{ maxWidth: 680 }}>
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <span className="card-title">Endpoint & Auth</span>
          </div>
          <form onSubmit={handleTest} style={{ padding: "16px 18px", display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={labelStyle}>Endpoint URL *</label>
              <input
                type="url"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="https://api.antaranews.com/news/v2"
                required
                style={inputStyle}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={labelStyle}>Autentikasi</label>
              <select value={authType} onChange={(e) => setAuthType(e.target.value as AuthType)} style={inputStyle}>
                <option value="none">Tidak ada</option>
                <option value="apikey">API Key (header)</option>
                <option value="bearer">Bearer Token</option>
              </select>
            </div>

            {authType !== "none" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={labelStyle}>{authType === "apikey" ? "API Key" : "Bearer Token"}</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={authType === "apikey" ? "X-API-Key: …" : "Bearer eyJ…"}
                  style={inputStyle}
                />
              </div>
            )}

            <div style={{ borderTop: "1px solid var(--line)", paddingTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
              <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: "var(--fg-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Field Mapping (JSON path)
              </p>
              {[
                { label: "Title path", value: titlePath, set: setTitlePath, placeholder: "articles[].title" },
                { label: "URL path", value: urlPath, set: setUrlPath, placeholder: "articles[].url" },
                { label: "Published date path", value: datePath, set: setDatePath, placeholder: "articles[].published_at" },
              ].map(({ label, value, set, placeholder }) => (
                <div key={label} style={{ display: "grid", gridTemplateColumns: "140px 1fr", alignItems: "center", gap: 12 }}>
                  <span style={{ fontSize: 12.5, color: "var(--fg-muted)" }}>{label}</span>
                  <input
                    type="text"
                    value={value}
                    onChange={(e) => set(e.target.value)}
                    placeholder={placeholder}
                    style={{ ...inputStyle, fontFamily: "var(--font-mono)", fontSize: 12 }}
                  />
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn" disabled={testStatus === "loading"}>
                {testStatus === "loading" ? "Menghubungi…" : "Test Koneksi"}
              </button>
              {testStatus === "ok" && (
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

        {testStatus === "ok" && (
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-head">
              <span className="card-title">Response Preview</span>
              <span className="badge badge-ok" style={{ marginLeft: "auto" }}>200 ok</span>
            </div>
            <div style={{ padding: "12px 14px" }}>
              <div style={{ marginBottom: 10, fontSize: 12.5, color: "var(--fg-muted)" }}>
                <strong style={{ color: "var(--fg)" }}>{PREVIEW_RESPONSE.total}</strong> artikel ditemukan · 2 ditampilkan
              </div>
              <table className="table" style={{ fontSize: 12.5 }}>
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>URL</th>
                    <th>Published</th>
                  </tr>
                </thead>
                <tbody>
                  {PREVIEW_RESPONSE.articles.map((a) => (
                    <tr key={a.id}>
                      <td>{a.title}</td>
                      <td className="mono faint" style={{ fontSize: 11 }}>{a.url}</td>
                      <td className="mono faint" style={{ fontSize: 11 }}>{a.published_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {saveStatus === "ok" && (
          <div style={{ padding: "12px 16px", borderRadius: "var(--radius)", background: "var(--ok-soft)", color: "oklch(0.42 0.13 155)", fontSize: 13, fontWeight: 500 }}>
            ✓ API source berhasil ditambahkan dan akan diingest pada run berikutnya.
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
