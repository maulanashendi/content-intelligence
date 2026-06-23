import { describe, test, expect } from "bun:test"
import { BentoCardSchema, BentoListResponseSchema } from "../src/schemas.js"

const VALID_CARD = {
  id: "a1b2c3d4-0001-4000-8000-000000000001",
  label: "Koalisi partai jelang Pilpres 2029",
  editorial_quadrant: "opportunity",
  trend_velocity: 1.84,
  competitor_count: 12,
  trend_match_count: 8,
  member_count: 47,
  views: 12450,
  internal_article_count: 3,
  last_competitor_at: "2026-06-23T05:00:00Z",
  last_internal_at: null,
}

describe("BentoCardSchema", () => {
  test("accepts a valid card", () => {
    expect(BentoCardSchema.safeParse(VALID_CARD).success).toBe(true)
  })
  test("rejects a card missing views", () => {
    const { views: _views, ...noViews } = VALID_CARD
    expect(BentoCardSchema.safeParse(noViews).success).toBe(false)
  })
})

describe("BentoListResponseSchema", () => {
  test("accepts a valid envelope", () => {
    const ok = BentoListResponseSchema.safeParse({
      cards: [VALID_CARD],
      total: 1,
      served_at: "2026-06-23T05:00:00Z",
      is_stale: false,
      max_age_hours: 36,
    })
    expect(ok.success).toBe(true)
  })
})
