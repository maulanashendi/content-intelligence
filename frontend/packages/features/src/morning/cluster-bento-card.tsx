import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useClusterBento, useClusterVolumeTrend, clusterKeys } from "@ei-fe/api"
import type { BentoCard as BentoCardData } from "@ei-fe/api"
import { useQueryClient } from "@tanstack/react-query"
import { Button, Skeleton, ErrorState, EmptyState, VelocityBar } from "@ei-fe/ui"
import { QUADRANT_BY_KEY } from "./quadrants.js"
import { useElementWidth } from "./use-element-width.js"
import { buildSparkline } from "./sparkline.js"

const PAGE = 8

const _relFmt = new Intl.RelativeTimeFormat("id-ID", { numeric: "auto" })

function relTime(iso: string | null): string {
  if (!iso) return "—"
  const then = new Date(/Z|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z").getTime()
  const diffMs = then - Date.now()
  const absMs = Math.abs(diffMs)
  if (absMs < 3600000) return _relFmt.format(Math.round(diffMs / 60000), "minute")
  if (absMs < 86400000) return _relFmt.format(Math.round(diffMs / 3600000), "hour")
  return _relFmt.format(Math.round(diffMs / 86400000), "day")
}

function fmtViews(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(".0", "") + "k"
  return String(n)
}

function quadrantStyle(key: string | null) {
  const def = (key && QUADRANT_BY_KEY[key]) || null
  return {
    label: def?.label ?? "Lainnya",
    bg: def?.bg ?? "var(--bg-sunken)",
    color: def?.countColor ?? "var(--fg-muted)",
  }
}

function Sparkline({ values }: { values: number[] }) {
  const [ref, width] = useElementWidth<HTMLDivElement>()
  const height = 48
  const model = width > 0 ? buildSparkline(values, { width, height, pad: 4 }) : null
  return (
    <div ref={ref} style={{ width: "100%" }}>
      {model && (
        <svg width="100%" height={height} role="img" aria-label="Tren volume kompetitor 48 jam">
          <path d={model.areaPath} fill="var(--accent-soft)" stroke="none" />
          <path d={model.linePath} fill="none" stroke="var(--accent)" strokeWidth={1.5} strokeLinejoin="round" />
          <circle cx={model.lastX} cy={model.lastY} r={2.4} fill="var(--accent)" />
        </svg>
      )}
    </div>
  )
}

function Stat({ k, v }: { k: string; v: string | number }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "4px 0", fontSize: 12.5 }}>
      <span style={{ color: "var(--fg-muted)" }}>{k}</span>
      <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums", color: "var(--fg)" }}>{v}</span>
    </div>
  )
}

function BentoCard({ card, open, onToggle }: { card: BentoCardData; open: boolean; onToggle: () => void }) {
  const navigate = useNavigate()
  const q = quadrantStyle(card.editorial_quadrant)
  const series = useClusterVolumeTrend(card.id, open)
  const values = (series.data?.buckets ?? []).map((b) => b.competitor_count)

  return (
    <article
      role="button"
      tabIndex={0}
      aria-expanded={open}
      onClick={() => onToggle()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onToggle()
        }
      }}
      style={{
        gridColumn: open ? "span 2" : "span 1",
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        padding: "14px 15px",
        cursor: "pointer",
        boxShadow: open ? "var(--shadow-md)" : "var(--shadow-sm)",
        transition: "box-shadow .2s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span
          style={{
            fontSize: 10.5,
            fontWeight: 700,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            padding: "3px 9px",
            borderRadius: 999,
            background: q.bg,
            color: q.color,
          }}
        >
          {q.label}
        </span>
        <span style={{ color: "var(--fg-faint)", fontSize: 13, lineHeight: 1 }}>{open ? "－" : "＋"}</span>
      </div>

      <h3
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 16,
          lineHeight: 1.2,
          fontWeight: 600,
          margin: "10px 0 0",
          color: "var(--fg)",
          ...(open ? {} : { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", minHeight: "2.4em" }),
        }}
      >
        {card.label ?? "Belum dilabeli"}
      </h3>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
        <span style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-faint)" }}>
          velocity
        </span>
        <div style={{ flex: 1 }}>
          <VelocityBar velocity={card.trend_velocity} max={3} />
        </div>
      </div>

      {open && (
        <div
          style={{
            marginTop: 14,
            paddingTop: 14,
            borderTop: "1px solid var(--line)",
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1.1fr",
            gap: 18,
          }}
        >
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-faint)", marginBottom: 6 }}>
              Permintaan
            </div>
            <Stat k="Kompetitor" v={card.competitor_count ?? 0} />
            <Stat k="Trend" v={card.trend_match_count ?? 0} />
            <Stat k="Artikel" v={card.member_count ?? 0} />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-faint)", marginBottom: 6 }}>
              Liputan kita
            </div>
            <Stat k="Artikel kita" v={card.internal_article_count} />
            <Stat k="Views" v={fmtViews(card.views)} />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--fg-faint)", marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
              <span>Kompetitor</span>
              <span style={{ color: "var(--fg-muted)" }}>48 jam</span>
            </div>
            {series.isLoading && <Skeleton className="w-full h-[48px]" />}
            {!series.isLoading && <Sparkline values={values} />}
            <div style={{ marginTop: 8, fontSize: 11.5, color: "var(--fg-muted)", lineHeight: 1.5 }}>
              Kompetitor terakhir <b style={{ color: "var(--fg)" }}>{relTime(card.last_competitor_at)}</b>
              <br />
              Internal terakhir <b style={{ color: "var(--fg)" }}>{relTime(card.last_internal_at)}</b>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                navigate(`/clusters/${card.id}`)
              }}
              style={{
                marginTop: 10,
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "var(--accent)",
                fontSize: 12.5,
                fontWeight: 600,
                padding: 0,
              }}
            >
              Buka klaster →
            </button>
          </div>
        </div>
      )}
    </article>
  )
}

export function ClusterBentoCard() {
  const [shown, setShown] = useState(PAGE)
  const [openId, setOpenId] = useState<string | null>(null)
  const qc = useQueryClient()
  const { data, isLoading, isError, error } = useClusterBento(shown)

  return (
    <div
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        padding: "18px 20px",
      }}
    >
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>Klaster Topik</div>
        <div style={{ fontSize: 12, color: "var(--fg-muted)", marginTop: 2 }}>
          Status &amp; kecepatan tiap klaster — klik kartu untuk detail
        </div>
      </div>

      {isLoading && <Skeleton className="w-full h-[280px]" />}
      {isError && (
        <ErrorState
          error={error}
          onRetry={() => qc.invalidateQueries({ queryKey: clusterKeys.bento(shown) })}
        />
      )}
      {!isLoading && !isError && data && data.cards.length === 0 && (
        <EmptyState
          title="Belum ada klaster."
          description="Grid terisi setelah cluster run harian (06:00 WIB) selesai."
        />
      )}
      {!isLoading && !isError && data && data.cards.length > 0 && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 14,
              alignItems: "start",
            }}
          >
            {data.cards.map((c) => (
              <BentoCard
                key={c.id}
                card={c}
                open={openId === c.id}
                onToggle={() => setOpenId((prev) => (prev === c.id ? null : c.id))}
              />
            ))}
          </div>
          {data.cards.length < data.total && (
            <div style={{ display: "flex", justifyContent: "center", marginTop: 18 }}>
              <Button variant="outline" size="md" onClick={() => setShown((s) => s + PAGE)}>
                Tampilkan {Math.min(PAGE, data.total - data.cards.length)} lagi · {data.cards.length} dari {data.total}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
