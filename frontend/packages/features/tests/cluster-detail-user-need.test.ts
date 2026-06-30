import { describe, test, expect } from "bun:test"
import { distributionToNeeds, CLUSTER_USER_NEED_ORDER } from "../src/cluster-detail/user-need-data.js"

describe("distributionToNeeds", () => {
  test("returns 8 axes normalized to the peak count", () => {
    const out = distributionToNeeds({ "Update me": 4, "Educate me": 2 })
    expect(out).toHaveLength(8)
    expect(out.map((n) => n.key)).toEqual(CLUSTER_USER_NEED_ORDER.map((n) => n.key))
    expect(out.find((n) => n.key === "Update me")!.value).toBe(100)  // peak
    expect(out.find((n) => n.key === "Educate me")!.value).toBe(50)
    expect(out.find((n) => n.key === "Divert me")!.value).toBe(0)
  })
  test("empty or null distribution → no chart data", () => {
    expect(distributionToNeeds(null)).toEqual([])
    expect(distributionToNeeds({})).toEqual([])
  })
})
