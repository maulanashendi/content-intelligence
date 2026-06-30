import { describe, test, expect } from "bun:test"
import { ClusterSummarySchema } from "../src/schemas.js"

const base = {
  id: "00000000-0000-0000-0000-000000000001",
  parent_cluster_id: null, label: "x", member_count: 1, is_current: true,
  created_at: "2026-06-30T00:00:00Z", trend_velocity: null, competitor_count: null,
  trend_match_count: null, weighted_trend_score: null, tempo_covered: null,
  last_internal_days_ago: null, underperformed: null, competitor_freshness_days: null,
  demand_score: null, high_demand: null, performance_level: null, editorial_quadrant: null,
  what_happened: null, parties_involved: null, editorial_angle: null,
  bullet_insights: null, insight_calculated_at: null,
}

describe("ClusterSummarySchema user-need distribution", () => {
  test("parses distribution + reps_tagged", () => {
    const out = ClusterSummarySchema.parse({
      ...base,
      user_need_distribution: { "Update me": 2, "Educate me": 1 },
      user_need_reps_tagged: 3,
    })
    expect(out.user_need_distribution).toEqual({ "Update me": 2, "Educate me": 1 })
    expect(out.user_need_reps_tagged).toBe(3)
  })
  test("accepts nulls", () => {
    const out = ClusterSummarySchema.parse({
      ...base, user_need_distribution: null, user_need_reps_tagged: null,
    })
    expect(out.user_need_distribution).toBeNull()
  })
})
