import { scaleBand, scaleLinear } from "d3"
import type { VolumeBucket } from "@ei-fe/api"

export interface ChartDims {
  width: number
  height: number
  padTop: number
  padRight: number
  padBottom: number
  padLeft: number
}

export interface Bar {
  index: number
  x: number
  width: number
  competitorY: number
  competitorH: number
  internalY: number
  internalH: number
  total: number
  bucket: VolumeBucket
}

export interface ChartModel {
  bars: Bar[]
  maxTotal: number
  innerWidth: number
  innerHeight: number
}

export function buildVolumeChart(buckets: VolumeBucket[], dims: ChartDims): ChartModel {
  const innerWidth = Math.max(0, dims.width - dims.padLeft - dims.padRight)
  const innerHeight = Math.max(0, dims.height - dims.padTop - dims.padBottom)
  const maxTotal = buckets.reduce(
    (m, b) => Math.max(m, b.competitor_count + b.internal_count),
    0,
  )

  const x = scaleBand<number>()
    .domain(buckets.map((_, i) => i))
    .range([0, innerWidth])
    .paddingInner(0.2)
    .paddingOuter(0.1)
  const y = scaleLinear().domain([0, maxTotal || 1]).range([innerHeight, 0])

  const bars: Bar[] = buckets.map((bucket, index) => {
    const competitorH = innerHeight - y(bucket.competitor_count)
    const internalH = innerHeight - y(bucket.internal_count)
    const competitorY = dims.padTop + innerHeight - competitorH
    const internalY = competitorY - internalH
    return {
      index,
      x: dims.padLeft + (x(index) ?? 0),
      width: x.bandwidth(),
      competitorY,
      competitorH,
      internalY,
      internalH,
      total: bucket.competitor_count + bucket.internal_count,
      bucket,
    }
  })

  return { bars, maxTotal, innerWidth, innerHeight }
}

const _dayFmt = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  timeZone: "Asia/Jakarta",
})
const _hourFmt = new Intl.DateTimeFormat("id-ID", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Asia/Jakarta",
})
const _tooltipFmt = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "Asia/Jakarta",
})

export function formatBucketLabel(iso: string, bucket: "hour" | "day"): string {
  const d = new Date(iso)
  return bucket === "day" ? _dayFmt.format(d) : _hourFmt.format(d)
}

export function formatBucketTooltip(iso: string): string {
  return `${_tooltipFmt.format(new Date(iso))} WIB`
}
