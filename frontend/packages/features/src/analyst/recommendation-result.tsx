import { useState } from "react"
import type { RecommendationOutput } from "@ei-fe/api"
import { ChevronRight } from "@ei-fe/ui"
import { activeFilters, inferNumericColumn, humanizeFilterKey } from "./data.js"
import { ResultCard, Section } from "./result-shell.js"
import { RankedBars } from "./ranked-bars.js"

const NEED_HINTS = ["user_need", "user_need_category", "need", "category"]

function inferNeedColumn(rows: Record<string, unknown>[]): string | null {
  const [first] = rows
  if (!first) return null
  const keys = Object.keys(first)
  return keys.find((k) => NEED_HINTS.includes(k.toLowerCase())) ?? null
}

function RawDataTable({ rows }: { rows: Record<string, unknown>[] }) {
  const [open, setOpen] = useState(false)
  const [firstRow] = rows
  const cols = firstRow ? Object.keys(firstRow) : []

  return (
    <Section title="Data mentah">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-[12px] rounded-[4px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
        style={{ color: "var(--fg-muted)", background: "none", border: "none", cursor: "pointer", padding: 0, fontFamily: "var(--font-sans)" }}
        aria-expanded={open}
      >
        <ChevronRight
          size={13}
          style={{
            color: "var(--fg-faint)",
            transition: "transform 200ms ease",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
          }}
        />
        {open ? "Sembunyikan data mentah" : "Lihat data mentah"}
      </button>
      {open && (
        <div className="mt-3 overflow-x-auto rounded-[6px]" style={{ border: "1px solid var(--line)" }}>
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr>
                {cols.map((c) => (
                  <th
                    key={c}
                    className="text-left px-3 py-2 text-[11px] font-semibold"
                    style={{
                      fontFamily: "var(--font-sans)",
                      color: "var(--fg-faint)",
                      background: "var(--bg-sunken)",
                      borderBottom: "1px solid var(--line)",
                      letterSpacing: "0.01em",
                    }}
                  >
                    {humanizeFilterKey(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {cols.map((c) => {
                    const num = typeof r[c] === "number"
                    return (
                      <td
                        key={c}
                        className={`px-3 py-2 ${num ? "text-right tabular-nums" : ""}`}
                        style={{
                          borderBottom: "1px solid var(--line)",
                          fontFamily: num ? "var(--font-mono)" : "var(--font-sans)",
                          color: "var(--fg)",
                        }}
                      >
                        {num ? (r[c] as number).toLocaleString("id-ID") : String(r[c] ?? "—")}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}

export function RecommendationResultCard({ result }: { result: RecommendationOutput }) {
  const filters = activeFilters(result.filters_applied)
  const rows = result.sample_data
  const valueCol = inferNumericColumn(rows)
  const [firstRow] = rows
  const cols = firstRow ? Object.keys(firstRow) : []
  const labelCol = cols.find((c) => typeof firstRow?.[c] === "string") ?? cols[0] ?? ""
  const needCol = inferNeedColumn(rows) ?? undefined

  return (
    <ResultCard label="Rekomendasi" meta={`${result.data_source} · ${rows.length} baris`}>
      {/* Section 1: Applied filters */}
      <Section title="Filter diterapkan" noBorder>
        {filters.length ? (
          <div className="flex flex-wrap gap-1.5">
            {filters.map((f) => (
              <span
                key={f.key}
                className="inline-flex items-center gap-1 text-[11.5px] px-2.5 py-1 rounded-[var(--radius)]"
                style={{
                  fontFamily: "var(--font-sans)",
                  background: "var(--bg-sunken)",
                  border: "1px solid var(--line)",
                }}
              >
                <span style={{ color: "var(--fg-faint)" }}>{f.label}</span>
                <span style={{ color: "var(--fg)" }}>{f.value}</span>
              </span>
            ))}
          </div>
        ) : (
          <span className="text-[12px]" style={{ fontFamily: "var(--font-sans)", color: "var(--fg-faint)" }}>
            Tanpa filter — semua data.
          </span>
        )}
      </Section>

      {rows.length === 0 ? (
        <Section title="Data">
          <span className="text-[12px]" style={{ fontFamily: "var(--font-sans)", color: "var(--fg-faint)" }}>
            Tidak ada data untuk filter ini.
          </span>
        </Section>
      ) : (
        <>
          {/* Section 2: Ranked bars — hero */}
          {valueCol && (
            <Section
              title="Performa teratas"
              aside={humanizeFilterKey(valueCol)}
            >
              <RankedBars rows={rows} valueCol={valueCol} labelCol={labelCol} needCol={needCol} />
            </Section>
          )}

          {/* Section 3: Raw data table — collapsed by default */}
          <RawDataTable rows={rows} />
        </>
      )}

      {/* Section 4: Insights & actions */}
      {result.insights.length > 0 && (
        <Section title="Insight & aksi">
          <div className="flex flex-col gap-3">
            {result.insights.map((ins, i) => (
              <div
                key={i}
                className="py-3 px-3 rounded-[var(--radius)]"
                style={{ background: "var(--bg-sunken)", border: "1px solid var(--line)" }}
              >
                <p
                  className="text-[13px] font-semibold mb-1 m-0"
                  style={{ fontFamily: "var(--font-sans)", color: "var(--fg)" }}
                >
                  {ins.title}
                </p>
                <p
                  className="text-[12.5px] leading-relaxed m-0 mb-2"
                  style={{ fontFamily: "var(--font-sans)", color: "var(--fg-muted)" }}
                >
                  {ins.insight}
                </p>
                <div className="flex gap-1.5 items-baseline">
                  <span
                    className="text-[10px] font-semibold px-1.5 py-0.5 rounded-[4px] shrink-0"
                    style={{
                      fontFamily: "var(--font-sans)",
                      color: "var(--accent-fg)",
                      background: "var(--accent-soft)",
                    }}
                  >
                    Aksi
                  </span>
                  <span
                    className="text-[12.5px] leading-relaxed"
                    style={{ fontFamily: "var(--font-sans)", color: "var(--fg)" }}
                  >
                    {ins.action}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Section 5: Closing summary */}
      <div
        className="p-4"
        style={{
          borderTop: "1px solid var(--line)",
          background: "linear-gradient(180deg, oklch(0.98 0.01 262), var(--bg-elev))",
        }}
      >
        <p
          className="text-[11px] font-semibold mb-3"
          style={{ fontFamily: "var(--font-sans)", color: "var(--fg-muted)", letterSpacing: "0.02em" }}
        >
          Ringkasan
        </p>
        <p
          className="text-[14.5px] leading-relaxed m-0"
          style={{ fontFamily: "var(--font-serif)", color: "var(--fg)" }}
        >
          {result.summary}
        </p>
      </div>
    </ResultCard>
  )
}
