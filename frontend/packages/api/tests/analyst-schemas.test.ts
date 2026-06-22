import { describe, test, expect } from "bun:test"
import { AnalyzeResultSchema, RecommendationOutputSchema } from "../src/schemas.js"

const VALID_ANALYZE = {
  features: Object.fromEntries(
    [
      "f01_breaking","f02_live_developing","f03_timeless","f04_explanatory",
      "f05_data_investigative","f06_author_voice","f07_depth_analysis","f08_expert_quotes",
      "f09_emotional_positive","f10_conflict_tragedy","f11_light_humor","f12_actionable_steps",
      "f13_collective_call","f14_community_identity","f15_listicle_format","f16_social_buzz",
    ].map((k, i) => [k, { status: i % 2, reasoning: "alasan" }]),
  ),
  editorial_feedback: { recommendation_judul: ["A"], missing_info: [], bias_check: [], next_angle: ["B"] },
  user_needs: [{ category: "Educate me", score: 88 }, { category: "Help me", score: 25 }],
}

const VALID_RECO = {
  filters_applied: { category: "Ekonomi", days_lookback: 7 },
  sample_data: [{ judul: "Kurs Rupiah", page_views: 142300, user_need: "Update me" }],
  insights: [{ title: "T", insight: "I", action: "A" }],
  summary: "ringkasan",
  data_source: "airflow_json",
}

describe("AnalyzeResultSchema", () => {
  test("accepts a valid analyze payload", () => {
    expect(AnalyzeResultSchema.safeParse(VALID_ANALYZE).success).toBe(true)
  })
  test("rejects a feature missing reasoning", () => {
    const bad = structuredClone(VALID_ANALYZE)
    delete (bad.features.f01_breaking as { reasoning?: string }).reasoning
    expect(AnalyzeResultSchema.safeParse(bad).success).toBe(false)
  })
})

describe("RecommendationOutputSchema", () => {
  test("accepts a valid recommendation payload", () => {
    expect(RecommendationOutputSchema.safeParse(VALID_RECO).success).toBe(true)
  })
  test("accepts arbitrary sample_data row shapes", () => {
    const r = structuredClone(VALID_RECO)
    r.sample_data = [{ anything: 1 }, { else: "x", n: 2 }]
    expect(RecommendationOutputSchema.safeParse(r).success).toBe(true)
  })
})
