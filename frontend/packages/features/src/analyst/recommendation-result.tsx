import type { RecommendationOutput } from "@ei-fe/api"
import { activeFilters, inferNumericColumn, humanizeFilterKey } from "./data.js"
import { ResultCard, Section } from "./result-shell.js"
import { RankedBars } from "./ranked-bars.js"

export function RecommendationResultCard({ result }: { result: RecommendationOutput }) {
  const filters = activeFilters(result.filters_applied)
  const rows = result.sample_data
  const valueCol = inferNumericColumn(rows)
  const cols = rows.length ? Object.keys(rows[0]) : []
  const labelCol = cols.find((c) => typeof rows[0]?.[c] === "string") ?? cols[0] ?? ""

  return (
    <ResultCard kicker="Rekomendasi" meta={`data: ${result.data_source} · ${rows.length} baris`}>
      <Section title="Filter Diterapkan" noBorder>
        {filters.length ? (
          <div className="flex flex-wrap gap-1.5">
            {filters.map((f) => (
              <span key={f.key} className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-0.5 rounded-[5px]" style={{ fontFamily: "var(--font-mono)", background: "var(--bg-sunken)", border: "1px solid var(--line)", color: "var(--fg-muted)" }}>
                <span style={{ color: "var(--fg-faint)" }}>{f.label}</span><span style={{ color: "var(--fg)" }}>{f.value}</span>
              </span>
            ))}
          </div>
        ) : <span className="text-[12px]" style={{ color: "var(--fg-faint)" }}>Tanpa filter — semua data.</span>}
      </Section>

      {rows.length === 0 ? (
        <Section title="Data"><span className="text-[12px]" style={{ color: "var(--fg-faint)" }}>Tidak ada data untuk filter ini.</span></Section>
      ) : (
        <>
          {valueCol && (
            <Section title={`Teratas · ${humanizeFilterKey(valueCol)}`}>
              <RankedBars rows={rows} valueCol={valueCol} labelCol={labelCol} />
            </Section>
          )}
          <Section title="Data Mentah">
            <div className="overflow-x-auto rounded-[6px]" style={{ border: "1px solid var(--line)" }}>
              <table className="w-full border-collapse text-[12.5px]">
                <thead>
                  <tr>{cols.map((c) => (
                    <th key={c} className="text-left px-3 py-2 text-[9.5px] uppercase tracking-[0.05em] font-medium" style={{ color: "var(--fg-faint)", background: "var(--bg-sunken)", borderBottom: "1px solid var(--line)" }}>{humanizeFilterKey(c)}</th>
                  ))}</tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={i}>{cols.map((c) => {
                      const num = typeof r[c] === "number"
                      return <td key={c} className={`px-3 py-2 ${num ? "text-right tabular-nums" : ""}`} style={{ borderBottom: "1px solid var(--line)", fontFamily: num ? "var(--font-mono)" : undefined }}>{num ? (r[c] as number).toLocaleString("id-ID") : String(r[c] ?? "—")}</td>
                    })}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}

      {result.insights.length > 0 && (
        <Section title="Insight & Aksi">
          <div className="flex flex-col">
            {result.insights.map((ins, i) => (
              <div key={i} className="py-3" style={i > 0 ? { borderTop: "1px dashed var(--line)" } : undefined}>
                <p className="text-[13px] font-semibold mb-1" style={{ color: "var(--fg)" }}>{ins.title}</p>
                <p className="text-[12.5px] leading-relaxed m-0" style={{ color: "var(--fg-muted)" }}>{ins.insight}</p>
                <div className="flex gap-1.5 items-baseline mt-1.5">
                  <span className="text-[9px] uppercase tracking-[0.05em] px-1.5 py-0.5 rounded-[4px] shrink-0" style={{ fontFamily: "var(--font-mono)", color: "var(--accent-fg)", background: "var(--accent-soft)" }}>aksi</span>
                  <span className="text-[12.5px] leading-relaxed" style={{ color: "var(--fg)" }}>{ins.action}</span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Ringkasan">
        <p className="text-[14.5px] leading-relaxed m-0" style={{ fontFamily: "var(--font-serif)", color: "var(--fg)" }}>{result.summary}</p>
      </Section>
    </ResultCard>
  )
}
