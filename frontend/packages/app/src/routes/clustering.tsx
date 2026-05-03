import { useState } from "react"
import { Link } from "react-router-dom"
import { TrendSignalCard } from "@ei-fe/features"

/* ── Dummy data matching exact schema ─────────────────────────────── */

const CLUSTER_RUN = {
  id: "cr-0001-4000-8000-000000000001",
  algorithm: "hdbscan" as const,
  algorithm_version: "0.8.33",
  params: {
    min_cluster_size: 5,
    min_samples: 3,
    cluster_selection_epsilon: 0.12,
    metric: "cosine",
    umap_n_components: 8,
    umap_n_neighbors: 15,
    umap_min_dist: 0.05,
  },
  started_at: "2025-04-30T05:58:04Z",
  finished_at: "2025-04-30T06:02:41Z",
  notes: "Daily morning run. 4,812 articles, 142 clusters formed, 14 recommended.",
}

type Rec = "trending" | "worth_writing" | "saturated"

interface ClusterRow {
  id: string
  label: string | null
  member_count: number
  is_current: boolean
  created_at: string
  insight: {
    trend_velocity: number | null
    novelty_score: number | null
    coverage_score: number | null
    recommendation: Rec | null
    summary: string | null
    calculated_at: string
  } | null
}

const CLUSTERS: ClusterRow[] = [
  { id: "ac-0001", label: "Kenaikan Harga BBM Pertamina", member_count: 23, is_current: true, created_at: "2025-04-30T06:00:12Z", insight: { trend_velocity: 87.5, novelty_score: 0.72, coverage_score: 0.31, recommendation: "trending", summary: "Pertamina menaikkan harga BBM non-subsidi. Kompetitor masih di level breaking news, belum ada analisis dampak mendalam.", calculated_at: "2025-04-30T06:01:55Z" } },
  { id: "ac-0002", label: "Sidang MK Sengketa Pilkada Kaltim", member_count: 18, is_current: true, created_at: "2025-04-30T06:00:14Z", insight: { trend_velocity: 71.2, novelty_score: 0.65, coverage_score: 0.44, recommendation: "worth_writing", summary: "Sengketa Pilkada Kaltim masuk tahap sidang MK. Coverage masih didominasi laporan sidang, belum ada sudut putusan dan implikasinya.", calculated_at: "2025-04-30T06:02:01Z" } },
  { id: "ac-0003", label: "Korupsi Dana Desa Jawa Tengah", member_count: 31, is_current: true, created_at: "2025-04-30T06:00:09Z", insight: { trend_velocity: 68.0, novelty_score: 0.88, coverage_score: 0.22, recommendation: "worth_writing", summary: "Kasus korupsi dana desa skala besar. Novelty sangat tinggi — mayoritas artikel wire-only, belum ada investigasi jaringan pelaku.", calculated_at: "2025-04-30T06:01:48Z" } },
  { id: "ac-0004", label: "Pengesahan UU PPRT DPR", member_count: 12, is_current: true, created_at: "2025-04-30T06:00:20Z", insight: { trend_velocity: 61.5, novelty_score: 0.55, coverage_score: 0.60, recommendation: "worth_writing", summary: "UU Perlindungan Pekerja Rumah Tangga disahkan DPR. Coverage moderat — sudut implementasi dan nasib PRT belum ditulis.", calculated_at: "2025-04-30T06:01:40Z" } },
  { id: "ac-0005", label: "Prabowo-Xi Jinping Bilateral Bali", member_count: 9, is_current: true, created_at: "2025-04-30T06:00:31Z", insight: { trend_velocity: 54.8, novelty_score: 0.41, coverage_score: 0.72, recommendation: "trending", summary: "Pertemuan bilateral Prabowo-Xi Jinping di Bali. Coverage tinggi tapi dangkal — belum ada analisis isi perjanjian.", calculated_at: "2025-04-30T06:01:33Z" } },
  { id: "ac-0006", label: "BPJS Kesehatan Iuran Kelas Baru", member_count: 15, is_current: true, created_at: "2025-04-30T06:00:17Z", insight: { trend_velocity: 48.3, novelty_score: 0.60, coverage_score: 0.38, recommendation: "worth_writing", summary: "Rencana BPJS Kesehatan mengubah sistem kelas. Masih banyak kebingungan publik yang belum terjawab di media.", calculated_at: "2025-04-30T06:01:28Z" } },
  { id: "ac-0007", label: "Kebakaran Hutan Kalimantan Barat", member_count: 7, is_current: true, created_at: "2025-04-30T06:00:44Z", insight: { trend_velocity: 44.1, novelty_score: 0.77, coverage_score: 0.28, recommendation: "worth_writing", summary: "Hotspot Kalbar meningkat tajam. Coverage masih wire dari BNPB saja, belum ada sudut dampak komunitas lokal.", calculated_at: "2025-04-30T06:01:20Z" } },
  { id: "ac-0008", label: "Startup Teknologi PHK Gelombang Kedua", member_count: 20, is_current: true, created_at: "2025-04-30T06:00:11Z", insight: { trend_velocity: 39.6, novelty_score: 0.49, coverage_score: 0.55, recommendation: "worth_writing", summary: "PHK startup gelombang kedua 2025. Beberapa nama besar belum muncul di coverage, data agregat belum dianalisis.", calculated_at: "2025-04-30T06:01:15Z" } },
  { id: "ac-0009", label: "Rupiah Melemah Terhadap Dolar AS", member_count: 11, is_current: true, created_at: "2025-04-30T06:00:08Z", insight: { trend_velocity: 35.2, novelty_score: 0.33, coverage_score: 0.81, recommendation: "worth_writing", summary: "Rupiah melemah menembus Rp 16.400/USD. Coverage jenuh di permukaan, tapi analisis penyebab struktural masih absen.", calculated_at: "2025-04-30T06:01:09Z" } },
  { id: "ac-0010", label: "Rekrutmen CPNS 2025 Kemenpan", member_count: 8, is_current: true, created_at: "2025-04-30T06:00:55Z", insight: { trend_velocity: 29.9, novelty_score: 0.58, coverage_score: 0.40, recommendation: "worth_writing", summary: "Rekrutmen CPNS 2025 dibuka kembali. Banyak pertanyaan publik soal formasi dan persyaratan belum dijawab media.", calculated_at: "2025-04-30T06:01:02Z" } },
  { id: "ac-0011", label: "Pemilu AS Dampak Ekonomi Indonesia", member_count: 45, is_current: false, created_at: "2025-04-29T06:01:03Z", insight: { trend_velocity: 22.1, novelty_score: 0.18, coverage_score: 0.94, recommendation: "saturated", summary: null, calculated_at: "2025-04-29T06:02:11Z" } },
  { id: "ac-0012", label: "Kasus Korupsi e-KTP Kelanjutan", member_count: 38, is_current: false, created_at: "2025-04-29T06:01:08Z", insight: { trend_velocity: 17.4, novelty_score: 0.12, coverage_score: 0.89, recommendation: "saturated", summary: null, calculated_at: "2025-04-29T06:02:18Z" } },
]


/* ── Helpers ──────────────────────────────────────────────────────── */

function parseIso(iso: string): Date {
  return /Z|[+-]\d{2}:?\d{2}$/.test(iso) ? new Date(iso) : new Date(iso + "Z")
}

function fmtTime(iso: string): string {
  return parseIso(iso).toLocaleString("id-ID", {
    day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }) + " WIB"
}

function duration(start: string, end: string | null): string {
  if (!end) return "—"
  const ms = parseIso(end).getTime() - parseIso(start).getTime()
  const s = Math.round(ms / 1000)
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`
}

const REC_CLASS: Record<Rec, string> = {
  trending: "badge badge-recommended",
  worth_writing: "badge badge-active",
  saturated: "badge badge-saturated",
}

const REC_LABEL: Record<Rec, string> = {
  trending: "recommended",
  worth_writing: "worth writing",
  saturated: "saturated",
}

/* ── Components ───────────────────────────────────────────────────── */

function RunInfoCard() {
  const [expanded, setExpanded] = useState(false)
  const dur = duration(CLUSTER_RUN.started_at, CLUSTER_RUN.finished_at)

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <span className="card-title">Cluster Run</span>
        <span className="badge badge-ok" style={{ marginLeft: 0 }}>latest</span>
        <span className="card-meta">{fmtTime(CLUSTER_RUN.started_at)}</span>
        <span className="faint mono" style={{ fontSize: 11, marginLeft: "auto" }}>
          {dur} · {CLUSTER_RUN.algorithm} {CLUSTER_RUN.algorithm_version}
        </span>
        <button
          className="btn btn-ghost"
          style={{ fontSize: 11.5, padding: "2px 8px" }}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "tutup" : "params"}
        </button>
      </div>

      <div style={{ padding: "10px 14px", display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {[
          { label: "Algoritma", value: CLUSTER_RUN.algorithm.toUpperCase() },
          { label: "Kluster terbentuk", value: String(CLUSTERS.filter(c => c.is_current).length) },
          { label: "Durasi run", value: dur },
          { label: "Selesai", value: fmtTime(CLUSTER_RUN.finished_at!) },
        ].map(({ label, value }) => (
          <div key={label}>
            <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--fg-faint)", fontWeight: 500, marginBottom: 2 }}>
              {label}
            </div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 500 }}>{value}</div>
          </div>
        ))}
      </div>

      {CLUSTER_RUN.notes && (
        <div style={{ padding: "0 14px 10px", fontSize: 12.5, color: "var(--fg-muted)", fontStyle: "italic", borderTop: "1px solid var(--line)", paddingTop: 8, marginTop: 2 }}>
          {CLUSTER_RUN.notes}
        </div>
      )}

      {expanded && (
        <div style={{ borderTop: "1px solid var(--line)", padding: "10px 14px" }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--fg-faint)", marginBottom: 8 }}>
            HDBSCAN params
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {Object.entries(CLUSTER_RUN.params).map(([k, v]) => (
              <div key={k} className="score-chip">
                <span className="lab">{k}</span>
                <span className="v">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ClusterList({ selected, onSelect }: { selected: string | null; onSelect: (id: string) => void }) {
  const current = CLUSTERS.filter(c => c.is_current)
  const archived = CLUSTERS.filter(c => !c.is_current)

  function renderRow(c: ClusterRow, i: number) {
    const ins = c.insight
    const isSelected = selected === c.id
    return (
      <tr
        key={c.id}
        className="row-clickable"
        onClick={() => onSelect(c.id)}
        style={isSelected ? { background: "var(--accent-soft)" } : undefined}
      >
        <td>
          <div style={{ fontFamily: "var(--font-serif)", fontSize: 14, fontWeight: 500, lineHeight: 1.3 }}>
            {c.label ?? "—"}
          </div>
          <div className="faint mono" style={{ fontSize: 10.5, marginTop: 2 }}>
            #{String(i + 1).padStart(4, "0")} · {CLUSTER_RUN.algorithm}
            {!c.is_current && <span style={{ marginLeft: 6, color: "var(--warn)" }}>archived</span>}
          </div>
        </td>
        <td>
          {ins?.recommendation ? (
            <span className={REC_CLASS[ins.recommendation]}>{REC_LABEL[ins.recommendation]}</span>
          ) : <span className="faint">—</span>}
        </td>
        <td>
          {ins?.trend_velocity != null ? (
            <div className="score-split" style={{ minWidth: 120 }}>
              <span className="score-num">{ins.trend_velocity.toFixed(1)}</span>
              <div className="score-bar">
                <span className="seg-p" style={{ width: `${Math.min(100, ins.trend_velocity)}%` }} />
              </div>
            </div>
          ) : <span className="faint mono" style={{ fontSize: 12 }}>—</span>}
        </td>
        <td className="num">{ins?.novelty_score != null ? Math.round(ins.novelty_score * 100) + "%" : "—"}</td>
        <td className="num">{ins?.coverage_score != null ? Math.round(ins.coverage_score * 100) + "%" : "—"}</td>
        <td className="num right">{c.member_count}</td>
        <td>
          <span
            className="badge"
            style={{
              background: c.is_current ? "var(--ok-soft)" : "var(--bg-sunken)",
              color: c.is_current ? "oklch(0.42 0.13 155)" : "var(--fg-faint)",
              borderColor: c.is_current ? "transparent" : "var(--line)",
            }}
          >
            {c.is_current ? "current" : "archived"}
          </span>
        </td>
      </tr>
    )
  }

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">Article Clusters</span>
        <span className="card-meta">{current.length} current · {archived.length} archived</span>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: "36%" }}>Label</th>
            <th>Insight</th>
            <th style={{ minWidth: 160 }}>Velocity</th>
            <th>Novelty</th>
            <th>Coverage</th>
            <th className="right">Artikel</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {current.map((c, i) => renderRow(c, i))}
          {archived.length > 0 && archived.map((c, i) => renderRow(c, current.length + i))}
        </tbody>
      </table>
    </div>
  )
}

function ClusterInsightPanel({ id }: { id: string }) {
  const c = CLUSTERS.find(c => c.id === id)
  if (!c) return null
  const ins = c.insight

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="card-head">
        <span className="card-title">Cluster Insight</span>
        {ins?.recommendation && (
          <span className={REC_CLASS[ins.recommendation]} style={{ marginLeft: 0 }}>
            {REC_LABEL[ins.recommendation]}
          </span>
        )}
      </div>
      <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <p style={{ fontFamily: "var(--font-serif)", fontSize: 17, fontWeight: 500, margin: "0 0 10px", letterSpacing: "-0.01em" }}>
            {c.label ?? "Tanpa label"}
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {[
              { lab: "Velocity", val: ins?.trend_velocity?.toFixed(1) ?? "—" },
              { lab: "Novelty", val: ins?.novelty_score != null ? Math.round(ins.novelty_score * 100) + "%" : "—" },
              { lab: "Coverage", val: ins?.coverage_score != null ? Math.round(ins.coverage_score * 100) + "%" : "—" },
              { lab: "Artikel", val: String(c.member_count) },
            ].map(({ lab, val }) => (
              <div key={lab} className="score-chip">
                <span className="lab">{lab}</span>
                <span className="v">{val}</span>
              </div>
            ))}
          </div>
        </div>

        {ins?.summary && (
          <div style={{ padding: "10px 12px", background: "var(--bg-sunken)", borderRadius: "var(--radius)", borderLeft: "3px solid var(--accent)" }}>
            <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--accent-fg)", fontWeight: 600, marginBottom: 4 }}>
              AI Summary
            </div>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "var(--fg-muted)", fontFamily: "var(--font-serif)" }}>
              {ins.summary}
            </p>
          </div>
        )}

        <div style={{ borderTop: "1px solid var(--line)", paddingTop: 10, display: "flex", gap: 16 }}>
          <span className="faint mono" style={{ fontSize: 11 }}>
            run: <span style={{ color: "var(--fg)" }}>{CLUSTER_RUN.algorithm} {CLUSTER_RUN.algorithm_version}</span>
          </span>
          <span className="faint mono" style={{ fontSize: 11 }}>
            scored: <span style={{ color: "var(--fg)" }}>{ins ? fmtTime(ins.calculated_at) : "—"}</span>
          </span>
          {c.is_current && (
            <Link to={`/clusters/${c.id}`} className="btn btn-ghost" style={{ fontSize: 11, padding: "1px 8px", marginLeft: "auto" }}>
              Detail →
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── Page ─────────────────────────────────────────────────────────── */

export function ClusteringRoute() {
  const [selectedId, setSelectedId] = useState<string | null>(CLUSTERS[0]?.id ?? null)

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Topic <span className="serif">Clustering</span></h1>
          <p className="page-sub">
            Hasil clustering run terbaru — {CLUSTERS.filter(c => c.is_current).length} kluster aktif
          </p>
        </div>
        <div className="page-actions">
          <span className="faint mono" style={{ fontSize: 11.5 }}>
            Run {CLUSTER_RUN.id.slice(0, 8)} · {duration(CLUSTER_RUN.started_at, CLUSTER_RUN.finished_at)}
          </span>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 280px",
          gap: 20,
          padding: "20px 28px 48px",
          alignItems: "start",
        }}
      >
        {/* Left: run info + cluster list + insight panel */}
        <div>
          <RunInfoCard />
          <ClusterList selected={selectedId} onSelect={setSelectedId} />
          {selectedId && <ClusterInsightPanel id={selectedId} />}
        </div>

        {/* Right: trend signals */}
        <TrendSignalCard sticky />
      </div>
    </>
  )
}
