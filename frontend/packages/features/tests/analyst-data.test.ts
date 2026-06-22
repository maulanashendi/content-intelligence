import { describe, test, expect } from "bun:test"
import {
  orderedUserNeeds, groupedFeatures, radarPoints, inferNumericColumn,
  activeFilters, USER_NEED_ORDER, FEATURE_ANCHORS,
} from "../src/analyst/data.js"

describe("orderedUserNeeds", () => {
  test("returns the 6 needs in fixed order with ID labels", () => {
    const out = orderedUserNeeds([{ category: "Educate me", score: 88 }])
    expect(out).toHaveLength(6)
    expect(out.map((n) => n.label)).toEqual(USER_NEED_ORDER.map((n) => n.label))
    expect(out.find((n) => n.key === "Educate me")!.value).toBe(88)
    expect(out.find((n) => n.key === "Help me")!.value).toBe(0) // missing → 0
  })
  test("normalizes 0–1 scores to 0–100", () => {
    const out = orderedUserNeeds([
      { category: "Educate me", score: 0.88 },
      { category: "Help me", score: 0.25 },
    ])
    expect(out.find((n) => n.key === "Educate me")!.value).toBe(88)
  })
})

describe("groupedFeatures", () => {
  test("groups 16 features into 4 anchors and counts detected", () => {
    const feats = Object.fromEntries(
      FEATURE_ANCHORS.flatMap((a) => a.keys).map((k, i) => [k, { status: i < 5 ? 1 : 0, reasoning: "r" }]),
    )
    const groups = groupedFeatures(feats as never)
    expect(groups).toHaveLength(4)
    expect(groups.reduce((s, g) => s + g.flags.length, 0)).toBe(16)
    expect(groups.reduce((s, g) => s + g.detected, 0)).toBe(5)
  })
})

describe("radarPoints", () => {
  test("first axis points straight up from center", () => {
    const pts = radarPoints([100, 0, 0, 0, 0, 0], 100, 100, 80)
    expect(pts[0][0]).toBeCloseTo(100, 1) // same x as center
    expect(pts[0][1]).toBeCloseTo(20, 1)  // cy - r
  })
})

describe("inferNumericColumn", () => {
  test("prefers a views-like column", () => {
    expect(inferNumericColumn([{ judul: "a", page_views: 10, x: 3 }])).toBe("page_views")
  })
  test("falls back to first numeric column", () => {
    expect(inferNumericColumn([{ judul: "a", skor: 5 }])).toBe("skor")
  })
  test("returns null when no numeric column", () => {
    expect(inferNumericColumn([{ judul: "a", kategori: "b" }])).toBeNull()
  })
})

describe("activeFilters", () => {
  test("humanizes keys and skips null", () => {
    const out = activeFilters({ category: "Ekonomi", days_lookback: 7, author: null })
    expect(out.map((f) => f.key)).toEqual(["category", "days_lookback"])
    expect(out[0].label).toBe("kategori")
  })
})
