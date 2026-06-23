import { useLayoutEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useVolumeTrend, articleKeys } from "@ei-fe/api"
import { Skeleton, ErrorState, EmptyState } from "@ei-fe/ui"
import { buildVolumeChart, formatBucketLabel, formatBucketTooltip, type Bar } from "./volume-chart.js"

const HEIGHT = 260
const PAD = { padTop: 12, padRight: 14, padBottom: 28, padLeft: 36 }
const COMPETITOR_COLOR = "var(--fg-faint)"
const INTERNAL_COLOR = "var(--accent)"

function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    setWidth(el.getBoundingClientRect().width)
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) setWidth(e.contentRect.width)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

function LegendDot({ color }: { color: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 9,
        height: 9,
        borderRadius: 2,
        background: color,
        marginRight: 5,
        verticalAlign: "middle",
      }}
    />
  )
}

function Toggle({
  bucket,
  onChange,
}: {
  bucket: "hour" | "day"
  onChange: (b: "hour" | "day") => void
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 3,
        background: "var(--bg-sunken)",
        padding: 3,
        borderRadius: "var(--radius)",
      }}
    >
      {(["hour", "day"] as const).map((b) => (
        <button
          key={b}
          type="button"
          aria-pressed={bucket === b}
          onClick={() => onChange(b)}
          style={{
            border: "none",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 500,
            padding: "4px 14px",
            borderRadius: 4,
            background: bucket === b ? "var(--bg-elev)" : "transparent",
            color: bucket === b ? "var(--fg)" : "var(--fg-muted)",
            boxShadow: bucket === b ? "var(--shadow-sm)" : "none",
          }}
        >
          {b === "hour" ? "Jam" : "Hari"}
        </button>
      ))}
    </div>
  )
}

function Tooltip({ bar, containerWidth }: { bar: Bar; containerWidth: number }) {
  const left = Math.min(Math.max(bar.x + bar.width / 2, 80), containerWidth - 80)
  return (
    <div
      style={{
        position: "absolute",
        left,
        top: bar.internalY,
        transform: "translate(-50%, calc(-100% - 8px))",
        background: "var(--fg)",
        color: "var(--bg-elev)",
        padding: "6px 10px",
        borderRadius: 6,
        fontSize: 11.5,
        lineHeight: 1.55,
        whiteSpace: "nowrap",
        pointerEvents: "none",
        boxShadow: "var(--shadow-md)",
        zIndex: 10,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 2 }}>
        {formatBucketTooltip(bar.bucket.bucket_start)}
      </div>
      <div>
        <LegendDot color={INTERNAL_COLOR} />
        Internal: {bar.bucket.internal_count}
      </div>
      <div>
        <LegendDot color={COMPETITOR_COLOR} />
        Kompetitor: {bar.bucket.competitor_count}
      </div>
      <div style={{ marginTop: 2, opacity: 0.85 }}>Total: {bar.total}</div>
    </div>
  )
}

function Chart({
  width,
  bucket,
  buckets,
}: {
  width: number
  bucket: "hour" | "day"
  buckets: { bucket_start: string; competitor_count: number; internal_count: number }[]
}) {
  const [hover, setHover] = useState<number | null>(null)
  const model = buildVolumeChart(buckets, { width, height: HEIGHT, ...PAD })
  const { bars, maxTotal, innerHeight, innerWidth } = model
  const labelEvery = Math.max(1, Math.ceil(bars.length / 10))
  const yTicks = Array.from(new Set([0, Math.round(maxTotal / 2), maxTotal]))
  const plotRight = PAD.padLeft + innerWidth

  return (
    <div style={{ position: "relative", height: HEIGHT }}>
      <svg width="100%" height={HEIGHT} role="img" aria-label="Grafik volume berita kompetitor dan internal">
        {yTicks.map((t) => {
          const yPix = PAD.padTop + innerHeight - (maxTotal ? (innerHeight * t) / maxTotal : 0)
          return (
            <g key={t}>
              <line
                x1={PAD.padLeft}
                x2={plotRight}
                y1={yPix}
                y2={yPix}
                stroke="var(--line)"
                strokeDasharray="2 3"
              />
              <text x={PAD.padLeft - 8} y={yPix + 3} textAnchor="end" fontSize={10} fill="var(--fg-faint)">
                {t}
              </text>
            </g>
          )
        })}

        {bars.map((bar) => {
          const active = hover === null || hover === bar.index
          return (
            <g
              key={bar.index}
              onMouseEnter={() => setHover(bar.index)}
              onMouseLeave={() => setHover((h) => (h === bar.index ? null : h))}
            >
              <rect x={bar.x} y={PAD.padTop} width={bar.width} height={innerHeight} fill="transparent" />
              <rect
                x={bar.x}
                y={bar.competitorY}
                width={bar.width}
                height={bar.competitorH}
                fill={COMPETITOR_COLOR}
                rx={1}
                opacity={active ? 1 : 0.45}
              />
              <rect
                x={bar.x}
                y={bar.internalY}
                width={bar.width}
                height={bar.internalH}
                fill={INTERNAL_COLOR}
                rx={1}
                opacity={active ? 1 : 0.45}
              />
            </g>
          )
        })}

        {bars.map((bar) =>
          bar.index % labelEvery === 0 ? (
            <text
              key={bar.index}
              x={bar.x + bar.width / 2}
              y={HEIGHT - 8}
              textAnchor="middle"
              fontSize={10}
              fill="var(--fg-faint)"
            >
              {formatBucketLabel(bar.bucket.bucket_start, bucket)}
            </text>
          ) : null,
        )}
      </svg>

      {hover !== null && bars[hover] && <Tooltip bar={bars[hover]} containerWidth={width} />}
    </div>
  )
}

export function NewsVolumeTrendCard() {
  const [bucket, setBucket] = useState<"hour" | "day">("day")
  const qc = useQueryClient()
  const [ref, width] = useElementWidth<HTMLDivElement>()
  const { data, isLoading, isError, error } = useVolumeTrend(bucket)

  const isEmpty =
    data != null &&
    data.buckets.every(
      (b: { competitor_count: number; internal_count: number }) =>
        b.competitor_count + b.internal_count === 0,
    )

  return (
    <div
      ref={ref}
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        padding: "18px 20px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: 10,
          gap: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>Volume Berita</div>
          <div style={{ fontSize: 12, color: "var(--fg-muted)", marginTop: 2 }}>
            Kompetitor &amp; internal — lonjakan berita dari waktu ke waktu
          </div>
        </div>
        <Toggle bucket={bucket} onChange={setBucket} />
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 8, fontSize: 11.5, color: "var(--fg-muted)" }}>
        <span>
          <LegendDot color={INTERNAL_COLOR} />
          Internal (Tempo)
        </span>
        <span>
          <LegendDot color={COMPETITOR_COLOR} />
          Kompetitor (RSS)
        </span>
      </div>

      {isLoading && <Skeleton className="w-full h-[260px]" />}
      {isError && (
        <ErrorState
          error={error}
          onRetry={() => qc.invalidateQueries({ queryKey: articleKeys.volumeTrend(bucket) })}
        />
      )}
      {!isLoading && !isError && isEmpty && (
        <EmptyState
          title="Belum ada data volume berita."
          description="Grafik terisi setelah artikel masuk pada rentang waktu ini."
        />
      )}
      {!isLoading && !isError && data && !isEmpty && width > 0 && (
        <Chart width={width} bucket={bucket} buckets={data.buckets} />
      )}
    </div>
  )
}
