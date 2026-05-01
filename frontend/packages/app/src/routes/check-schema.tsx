import { useState } from "react"

const EXPECTED_FIELDS = [
  { field: "id", type: "string (uuid)", required: true },
  { field: "title", type: "string", required: true },
  { field: "url", type: "string (url)", required: true },
  { field: "published_at", type: "string (ISO 8601)", required: true },
  { field: "source_name", type: "string", required: true },
  { field: "first_paragraph", type: "string | null", required: false },
  { field: "relevance_score", type: "number 0–1 | null", required: false },
]

const SAMPLE_JSON = JSON.stringify(
  {
    id: "a1b2c3d4-0001-4000-8000-000000000001",
    title: "Pertamina Naikkan Harga BBM Non-Subsidi",
    url: "https://kompas.com/berita/001",
    published_at: "2025-04-30T07:12:00Z",
    source_name: "Kompas",
    first_paragraph: "PT Pertamina (Persero) resmi menaikkan harga BBM…",
    relevance_score: 0.97,
  },
  null,
  2,
)

type CheckStatus = "idle" | "loading" | "pass" | "fail"

interface FieldResult {
  field: string
  status: "ok" | "missing" | "wrong_type" | "unexpected"
  detail?: string
}

export function CheckSchemaRoute() {
  const [input, setInput] = useState(SAMPLE_JSON)
  const [source, setSource] = useState<"article" | "cluster">("article")
  const [status, setStatus] = useState<CheckStatus>("idle")
  const [results, setResults] = useState<FieldResult[]>([])
  const [parseError, setParseError] = useState<string | null>(null)

  function handleCheck() {
    setParseError(null)
    setStatus("loading")

    setTimeout(() => {
      let parsed: Record<string, unknown>
      try {
        parsed = JSON.parse(input)
      } catch (e) {
        setParseError("JSON tidak valid: " + (e as Error).message)
        setStatus("idle")
        return
      }

      const fields = source === "article" ? EXPECTED_FIELDS : CLUSTER_FIELDS
      const out: FieldResult[] = fields.map(({ field, type, required }) => {
        if (!(field in parsed)) {
          return required
            ? { field, status: "missing", detail: "field wajib tidak ada" }
            : { field, status: "ok", detail: "opsional · tidak ada (ok)" }
        }
        const val = parsed[field]
        if (type.includes("uuid") && typeof val !== "string") return { field, status: "wrong_type", detail: `diharapkan string, dapat ${typeof val}` }
        if (type === "string" && typeof val !== "string") return { field, status: "wrong_type", detail: `diharapkan string, dapat ${typeof val}` }
        if (type.includes("number") && typeof val !== "number" && val !== null) return { field, status: "wrong_type", detail: `diharapkan number|null, dapat ${typeof val}` }
        return { field, status: "ok" }
      })

      const unknowns = Object.keys(parsed).filter((k) => !fields.find((f) => f.field === k))
      unknowns.forEach((k) => out.push({ field: k, status: "unexpected", detail: "tidak dikenal" }))

      setResults(out)
      setStatus(out.some((r) => r.status === "missing" || r.status === "wrong_type") ? "fail" : "pass")
    }, 800)
  }

  const STATUS_ICON: Record<string, string> = { ok: "✓", missing: "✗", wrong_type: "!", unexpected: "?" }
  const STATUS_COLOR: Record<string, string> = {
    ok: "oklch(0.42 0.13 155)",
    missing: "var(--bad)",
    wrong_type: "var(--warn)",
    unexpected: "var(--fg-faint)",
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Check <span className="serif">Schema</span></h1>
          <p className="page-sub">Validasi JSON payload terhadap skema artikel atau kluster yang diharapkan</p>
        </div>
      </div>

      <div className="page-body" style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20, alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <div className="card-head">
              <span className="card-title">Input JSON</span>
              <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                {(["article", "cluster"] as const).map((t) => (
                  <button
                    key={t}
                    className={source === t ? "btn" : "btn btn-ghost"}
                    style={{ fontSize: 11.5, padding: "3px 8px" }}
                    onClick={() => setSource(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ padding: "12px 14px" }}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                rows={18}
                style={{
                  width: "100%",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  lineHeight: 1.6,
                  padding: "10px 12px",
                  border: "1px solid var(--line-strong)",
                  borderRadius: "var(--radius)",
                  background: "var(--bg-sunken)",
                  color: "var(--fg)",
                  outline: "none",
                  resize: "vertical",
                  boxSizing: "border-box",
                }}
              />
              {parseError && (
                <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--bad)", fontFamily: "var(--font-mono)" }}>{parseError}</p>
              )}
              <div style={{ marginTop: 10 }}>
                <button
                  className="btn"
                  onClick={handleCheck}
                  disabled={status === "loading"}
                  style={{ background: "var(--fg)", color: "var(--bg-elev)", borderColor: "var(--fg)" }}
                >
                  {status === "loading" ? "Memeriksa…" : "Periksa Schema"}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <div className="card-head">
              <span className="card-title">Skema yang diharapkan</span>
              <span className="badge badge-watching" style={{ marginLeft: "auto" }}>{source}</span>
            </div>
            <table className="table" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Tipe</th>
                  <th>Wajib</th>
                </tr>
              </thead>
              <tbody>
                {(source === "article" ? EXPECTED_FIELDS : CLUSTER_FIELDS).map((f) => (
                  <tr key={f.field}>
                    <td className="mono" style={{ fontSize: 11.5 }}>{f.field}</td>
                    <td className="faint mono" style={{ fontSize: 11 }}>{f.type}</td>
                    <td>{f.required ? <span className="badge badge-recommended">ya</span> : <span className="faint" style={{ fontSize: 11 }}>tidak</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {status !== "idle" && status !== "loading" && (
            <div className="card">
              <div className="card-head">
                <span className="card-title">Hasil</span>
                <span className={`badge ${status === "pass" ? "badge-ok" : "badge-saturated"}`} style={{ marginLeft: "auto" }}>
                  {status === "pass" ? "valid" : "ada error"}
                </span>
              </div>
              <table className="table" style={{ fontSize: 12 }}>
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr key={r.field}>
                      <td className="mono" style={{ fontSize: 11.5 }}>{r.field}</td>
                      <td>
                        <span style={{ color: STATUS_COLOR[r.status], fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
                          {STATUS_ICON[r.status]} {r.detail ?? r.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

const CLUSTER_FIELDS = [
  { field: "id", type: "string (uuid)", required: true },
  { field: "label", type: "string | null", required: false },
  { field: "member_count", type: "number | null", required: false },
  { field: "trend_velocity", type: "number | null", required: false },
  { field: "novelty_score", type: "number 0–1 | null", required: false },
  { field: "coverage_score", type: "number 0–1 | null", required: false },
  { field: "recommendation", type: '"trending"|"worth_writing"|"saturated"|null', required: false },
]
