import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { cn } from "@ei-fe/ui"
import { useQuadrantSummary, useClustersByQuadrant } from "@ei-fe/api"
import type { ClusterSummary } from "@ei-fe/api"
import { QUADRANTS, TOO_EARLY_DEF, type Quadrant, type QuadrantDef } from "./quadrants.js"

interface OpportunityMatrixCardProps {
  clusters: ClusterSummary[]
  dnaOn: boolean
}

// ─── Cluster row ─────────────────────────────────────────────────────────────

function ClusterRow({
  cluster,
  onNavigate,
}: {
  cluster: ClusterSummary
  onNavigate: (id: string) => void
}) {
  return (
    <button
      onClick={() => onNavigate(cluster.id)}
      className="flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left transition-colors"
      style={{ background: "transparent" }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLElement).style.background = "var(--bg-hover)"
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLElement).style.background = "transparent"
      }}
    >
      <div className="flex flex-1 flex-col gap-0.5 min-w-0">
        <span
          className="truncate text-[13px] font-medium leading-snug"
          style={{ color: "var(--fg)" }}
        >
          {cluster.label ?? (
            <span style={{ color: "var(--fg-faint)", fontStyle: "italic" }}>
              Belum dilabeli
            </span>
          )}
        </span>
        <span className="text-[11px]" style={{ color: "var(--fg-muted)" }}>
          {cluster.member_count} artikel
          {cluster.trend_match_count != null && cluster.trend_match_count > 0 && (
            <> · {cluster.trend_match_count} keyword trend</>
          )}
        </span>
      </div>
      {cluster.demand_score != null && (
        <div className="flex shrink-0 flex-col items-end gap-0.5">
          <span
            className="rounded px-1.5 py-0.5 text-[11px] font-semibold tabular-nums"
            style={{ background: "var(--accent-soft)", color: "var(--accent-fg)" }}
          >
            {(cluster.demand_score * 100).toFixed(0)}
          </span>
          <span className="text-[10px]" style={{ color: "var(--fg-ghost)" }}>demand</span>
        </div>
      )}
    </button>
  )
}

// ─── Panel ────────────────────────────────────────────────────────────────────

function QuadrantPanel({
  def,
  count,
  onClose,
  onNavigate,
  dnaOn,
}: {
  def: QuadrantDef | typeof TOO_EARLY_DEF
  count: number
  onClose: () => void
  onNavigate: (id: string) => void
  dnaOn: boolean
}) {
  const { data, isLoading } = useClustersByQuadrant(def.key, 8, dnaOn)
  const clusters = data?.clusters ?? []

  return (
    <div
      className="flex flex-col gap-4 rounded-lg p-4"
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--line-strong)",
        boxShadow: "var(--shadow-md)",
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-[18px] leading-none">{def.emoji}</span>
            <span className="text-[15px] font-semibold" style={{ color: "var(--fg)" }}>
              {def.label}
            </span>
            <span
              className="rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums"
              style={{ background: "var(--bg-sunken)", color: "var(--fg-muted)" }}
            >
              {count} topik
            </span>
          </div>
          <span
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: def.countColor ?? "var(--fg-muted)" }}
          >
            {def.action}
          </span>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 rounded p-1 text-[13px] leading-none"
          style={{ color: "var(--fg-muted)" }}
          onMouseEnter={(e) => {
            ;(e.currentTarget as HTMLElement).style.background = "var(--bg-hover)"
          }}
          onMouseLeave={(e) => {
            ;(e.currentTarget as HTMLElement).style.background = "transparent"
          }}
        >
          ✕
        </button>
      </div>

      {/* Description */}
      <p
        className="text-[13px] leading-relaxed"
        style={{ color: "var(--fg-muted)" }}
      >
        {def.description}
      </p>

      {/* Cluster list */}
      <div className="flex flex-col gap-0.5">
        <span
          className="mb-1 text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--fg-faint)" }}
        >
          Topik terkuat
        </span>
        {isLoading && (
          <div className="py-3 text-center text-[12px]" style={{ color: "var(--fg-faint)" }}>
            Memuat topik…
          </div>
        )}
        {!isLoading && clusters.length === 0 && (
          <div className="py-3 text-center text-[12px]" style={{ color: "var(--fg-faint)" }}>
            Tidak ada topik di kuadran ini.
          </div>
        )}
        {clusters.map((c) => (
          <ClusterRow key={c.id} cluster={c} onNavigate={onNavigate} />
        ))}
      </div>
    </div>
  )
}

// ─── Cell ─────────────────────────────────────────────────────────────────────

function QuadrantCell({
  def,
  count,
  active,
  onClick,
}: {
  def: QuadrantDef
  count: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col gap-1 rounded-md p-3 text-left transition-all",
        "hover:brightness-95 active:scale-[0.98]",
        active && "ring-2 ring-inset",
      )}
      style={{
        background: active ? def.activeBg : def.bg,
        border: `1px solid ${active ? def.activeBorder : def.border}`,
        ...(active ? { "--tw-ring-color": def.activeBorder } as React.CSSProperties : {}),
      }}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="text-[13px]" style={{ color: active ? "white" : "var(--fg)" }}>
          {def.emoji} {def.label}
        </span>
        <span
          className="text-[20px] font-semibold tabular-nums leading-none"
          style={{ color: active ? "white" : def.countColor }}
        >
          {count}
        </span>
      </div>
      <span
        className="text-[11px]"
        style={{ color: active ? "rgba(255,255,255,0.75)" : "var(--fg-muted)" }}
      >
        {def.sub}
      </span>
    </button>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function OpportunityMatrixCard({ clusters: _clusters, dnaOn }: OpportunityMatrixCardProps) {
  const navigate = useNavigate()
  const { data, isLoading } = useQuadrantSummary(dnaOn)
  const [selected, setSelected] = useState<Quadrant | null>(null)

  const counts = data ?? { opportunity: 0, winning: 0, evergreen: 0, ignore: 0, too_early: 0, total: 0 }
  const total = counts.total

  function toggle(q: Quadrant) {
    setSelected((prev) => (prev === q ? null : q))
  }

  const selectedDef =
    selected === "too_early"
      ? TOO_EARLY_DEF
      : selected != null
        ? QUADRANTS.find((q) => q.key === selected) ?? null
        : null

  return (
    <div className="flex flex-col gap-3">
      <div
        className="flex flex-col gap-3 rounded-lg p-4"
        style={{
          background: "var(--bg-elev)",
          border: "1px solid var(--line)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div className="flex items-baseline justify-between gap-2">
          <span
            className="text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: "var(--fg-muted)" }}
          >
            Matriks Peluang Editorial
          </span>
          <span className="text-[11px]" style={{ color: "var(--fg-faint)" }}>
            {isLoading ? "memuat…" : dnaOn ? `${total} topik · tema Tempo` : `${total} topik · semua cluster`}
          </span>
        </div>

        <div className="flex gap-2">
          <div className="flex flex-col justify-center">
            <span
              className="text-[10px] font-medium uppercase tracking-wider"
              style={{
                color: "var(--fg-ghost)",
                writingMode: "vertical-rl",
                transform: "rotate(180deg)",
                height: 80,
                textAlign: "center",
              }}
            >
              Demand ↑
            </span>
          </div>

          <div className="flex flex-1 flex-col gap-2">
            <div className="grid grid-cols-2 gap-1">
              <span />
              <div className="flex justify-around">
                <span
                  className="text-[10px] font-medium uppercase tracking-wider"
                  style={{ color: "var(--fg-ghost)" }}
                >
                  Performa Internal →
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {QUADRANTS.map((def) => (
                <QuadrantCell
                  key={def.key}
                  def={def}
                  count={counts[def.key]}
                  active={selected === def.key}
                  onClick={() => toggle(def.key)}
                />
              ))}
            </div>
          </div>
        </div>

        {counts.too_early > 0 && (
          <button
            onClick={() => toggle("too_early")}
            className={cn(
              "flex items-center gap-1.5 rounded px-2 py-1 text-left transition-colors",
              selected === "too_early"
                ? "bg-[var(--accent-soft)]"
                : "hover:bg-[var(--bg-hover)]",
            )}
          >
            <span className="text-[12px]">⏳</span>
            <span className="text-[12px]" style={{ color: "var(--fg-muted)" }}>
              <span className="font-medium" style={{ color: "var(--fg)" }}>
                {counts.too_early}
              </span>{" "}
              topik belum ada data GSC — artikel terlalu baru, pantau besok
            </span>
          </button>
        )}
      </div>

      {/* Inline panel — renders below the matrix when a quadrant is selected */}
      {selectedDef != null && (
        <QuadrantPanel
          def={selectedDef}
          count={counts[selectedDef.key]}
          onClose={() => setSelected(null)}
          onNavigate={(id) => {
            setSelected(null)
            navigate(`/clusters/${id}`)
          }}
          dnaOn={dnaOn}
        />
      )}
    </div>
  )
}
