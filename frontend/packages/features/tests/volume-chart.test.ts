import { describe, test, expect } from "bun:test"
import { buildVolumeChart, formatBucketLabel, formatBucketTooltip } from "../src/morning/volume-chart.js"

const DIMS = { width: 600, height: 200, padTop: 10, padRight: 10, padBottom: 30, padLeft: 30 }

function bkt(bucket_start: string, c: number, i: number) {
  return { bucket_start, competitor_count: c, internal_count: i, competitor_avg_per_source: c }
}

describe("buildVolumeChart", () => {
  test("one bar per bucket", () => {
    const m = buildVolumeChart([bkt("2026-06-22T17:00:00Z", 1, 2), bkt("2026-06-23T17:00:00Z", 0, 0)], DIMS)
    expect(m.bars).toHaveLength(2)
  })

  test("maxTotal is the largest stacked total", () => {
    const m = buildVolumeChart([bkt("a", 1, 1), bkt("b", 3, 2)], DIMS)
    expect(m.maxTotal).toBe(5)
  })

  test("tallest bar fills inner height; segments sum to it", () => {
    const m = buildVolumeChart([bkt("a", 2, 2)], DIMS) // total 4 == max
    const bar = m.bars[0]
    expect(bar.competitorH + bar.internalH).toBeCloseTo(m.innerHeight, 5)
  })

  test("internal stacks directly on top of competitor", () => {
    const m = buildVolumeChart([bkt("a", 3, 1)], DIMS)
    const bar = m.bars[0]
    expect(bar.internalY + bar.internalH).toBeCloseTo(bar.competitorY, 5)
  })

  test("a bar with double the total is twice as tall", () => {
    const m = buildVolumeChart([bkt("a", 1, 0), bkt("b", 2, 0)], DIMS)
    expect(m.bars[1].competitorH).toBeCloseTo(2 * m.bars[0].competitorH, 5)
  })

  test("all-zero buckets yield zero-height bars, no NaN", () => {
    const m = buildVolumeChart([bkt("a", 0, 0), bkt("b", 0, 0)], DIMS)
    for (const bar of m.bars) {
      expect(bar.competitorH).toBe(0)
      expect(bar.internalH).toBe(0)
      expect(Number.isNaN(bar.x)).toBe(false)
    }
  })

  test("bars run left→right inside the plot area", () => {
    const m = buildVolumeChart([bkt("a", 1, 0), bkt("b", 1, 0), bkt("c", 1, 0)], DIMS)
    expect(m.bars[0].x).toBeGreaterThanOrEqual(DIMS.padLeft)
    expect(m.bars[0].x).toBeLessThan(m.bars[1].x)
    expect(m.bars[2].x + m.bars[2].width).toBeLessThanOrEqual(DIMS.width - DIMS.padRight + 0.001)
  })
})

describe("formatBucketLabel", () => {
  test("day label is WIB day + Indonesian short month", () => {
    // 2026-06-11T17:00:00Z == 2026-06-12 00:00 WIB
    expect(formatBucketLabel("2026-06-11T17:00:00Z", "day")).toBe("12 Jun")
  })

  test("hour label is WIB 24h time", () => {
    // 2026-06-12T07:00:00Z == 2026-06-12 14:00 WIB
    expect(formatBucketLabel("2026-06-12T07:00:00Z", "hour")).toMatch(/^14[.:]00$/)
  })
})

describe("formatBucketTooltip", () => {
  test("includes the WIB suffix", () => {
    expect(formatBucketTooltip("2026-06-12T07:00:00Z")).toContain("WIB")
  })
})
