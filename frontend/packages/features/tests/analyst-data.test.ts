import { describe, test, expect } from "bun:test"
import {
  orderedUserNeeds, groupedFeatures, radarPoints, inferNumericColumn,
  activeFilters, USER_NEED_ORDER, FEATURE_ANCHORS, analyzeVerdict,
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

describe("analyzeVerdict", () => {
  // Build a full 6-need array from USER_NEED_ORDER with controlled values
  function makeNeeds(values: number[]): { key: string; label: string; value: number }[] {
    return USER_NEED_ORDER.map((n, i) => ({ key: n.key, label: n.label, value: values[i] ?? 0 }))
  }

  test("clear lead + weakest produces sentence containing both phrases", () => {
    // Edukasi=75 lead, Hibur=10 weakest, no strong secondary
    const needs = makeNeeds([30, 75, 40, 30, 30, 10])
    const result = analyzeVerdict(needs, 8)
    expect(result.leadLabel).toBe("Edukasi")
    expect(result.weakestLabel).toBe("Hibur")
    // sentence should mention both phrases
    expect(result.sentence).toContain("memahami persoalan")
    expect(result.sentence).toContain("terhibur")
    // Normal wording — should NOT contain flat-profile text
    expect(result.sentence).not.toContain("belum tajam")
  })

  test("flat profile (all values <40) produces 'belum tajam' wording", () => {
    const needs = makeNeeds([35, 38, 20, 15, 25, 10])
    const result = analyzeVerdict(needs, 3)
    expect(result.sentence).toContain("belum tajam")
    // The lead label (Edukasi=38) must appear
    expect(result.sentence).toContain("Edukasi")
  })

  test("secondary need included only when ≥50 and within 15 of lead", () => {
    // Lead: Beri tahu=80, 2nd: Edukasi=68 (≥50 and within 15) → included
    const needs = makeNeeds([80, 68, 30, 20, 20, 10])
    const withSecondary = analyzeVerdict(needs, 10)
    expect(withSecondary.sentence).toContain("memahami persoalan") // secondary phrase

    // Lead: Beri tahu=80, 2nd: Edukasi=60 (≥50 but NOT within 15: 80-60=20 > 15) → excluded
    const needs2 = makeNeeds([80, 60, 30, 20, 20, 10])
    const withoutSecondary = analyzeVerdict(needs2, 10)
    expect(withoutSecondary.sentence).not.toContain("memahami persoalan")

    // Lead: Beri tahu=80, 2nd: Edukasi=45 (within 15 but < 50) → excluded
    const needs3 = makeNeeds([80, 45, 30, 20, 20, 10])
    const withoutSecondary2 = analyzeVerdict(needs3, 10)
    expect(withoutSecondary2.sentence).not.toContain("memahami persoalan")
  })
})
