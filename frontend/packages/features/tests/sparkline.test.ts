import { describe, test, expect } from "bun:test"
import { buildSparkline } from "../src/morning/sparkline.js"

const DIMS = { width: 200, height: 50, pad: 4 }

describe("buildSparkline", () => {
  test("empty values produce empty paths and zero coords", () => {
    const m = buildSparkline([], DIMS)
    expect(m.linePath).toBe("")
    expect(m.areaPath).toBe("")
    expect(m.lastX).toBe(0)
    expect(m.lastY).toBe(0)
  })

  test("line path starts with a moveto and has one segment per point", () => {
    const m = buildSparkline([1, 2, 3], DIMS)
    expect(m.linePath.startsWith("M")).toBe(true)
    expect((m.linePath.match(/L/g) ?? []).length).toBe(2)
  })

  test("higher values map to smaller y (inverted screen axis)", () => {
    // ascending [0, 10]: last point is the max → y sits near the top (pad)
    const m = buildSparkline([0, 10], DIMS)
    expect(m.lastY).toBeCloseTo(DIMS.pad, 5)

    // ascending [0, 5, 10]: smaller values have larger screen-y (lower on screen)
    // point[0] (value 0) must have a larger y than point[2] (value 10)
    const m3 = buildSparkline([0, 5, 10], DIMS)
    const firstY = DIMS.height - DIMS.pad  // value 0 → baseline
    const lastY3 = DIMS.pad               // value 10 → top
    expect(m3.lastY).toBeCloseTo(lastY3, 5)
    // derive firstY from the 3-point model by parsing the first M command
    const firstMatch = m3.linePath.match(/^M[\d.]+ ([\d.]+)/)
    const parsedFirstY = firstMatch ? parseFloat(firstMatch[1]) : NaN
    expect(parsedFirstY).toBeCloseTo(firstY, 5)
    // the screen relationship: lower value → larger y coordinate
    expect(parsedFirstY).toBeGreaterThan(m3.lastY)
  })

  test("area path closes back to the baseline", () => {
    const m = buildSparkline([1, 2], DIMS)
    expect(m.areaPath.endsWith("Z")).toBe(true)
  })

  test("single point still yields a valid line path", () => {
    const m = buildSparkline([5], DIMS)
    expect(m.linePath.startsWith("M")).toBe(true)
  })
})
