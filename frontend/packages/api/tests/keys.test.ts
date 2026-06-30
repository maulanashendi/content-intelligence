import { describe, test, expect } from "bun:test"
import { clusterKeys } from "../src/keys.js"

describe("clusterKeys — dna param produces distinct cache keys", () => {
  test("morning: dna=true vs dna=false are distinct", () => {
    expect(clusterKeys.morning(true)).not.toEqual(clusterKeys.morning(false))
    expect(clusterKeys.morning(true)).toContain(true)
    expect(clusterKeys.morning(false)).toContain(false)
  })

  test("quadrantSummary: dna=true vs dna=false are distinct", () => {
    expect(clusterKeys.quadrantSummary(true)).not.toEqual(clusterKeys.quadrantSummary(false))
    expect(clusterKeys.quadrantSummary(true)).toContain(true)
    expect(clusterKeys.quadrantSummary(false)).toContain(false)
  })

  test("byQuadrant: dna=true vs dna=false are distinct (same quadrant)", () => {
    expect(clusterKeys.byQuadrant("high-demand-low-coverage", true)).not.toEqual(
      clusterKeys.byQuadrant("high-demand-low-coverage", false),
    )
    expect(clusterKeys.byQuadrant("high-demand-low-coverage", true)).toContain(true)
    expect(clusterKeys.byQuadrant("high-demand-low-coverage", false)).toContain(false)
  })

  test("bento: dna=true vs dna=false are distinct (same limit)", () => {
    expect(clusterKeys.bento(8, true)).not.toEqual(clusterKeys.bento(8, false))
    expect(clusterKeys.bento(8, true)).toContain(true)
    expect(clusterKeys.bento(8, false)).toContain(false)
  })

  test("keys share the same prefix (clusterKeys.all is a prefix of all)", () => {
    const prefix = clusterKeys.all
    expect(clusterKeys.morning(true).slice(0, prefix.length)).toEqual(prefix)
    expect(clusterKeys.quadrantSummary(true).slice(0, prefix.length)).toEqual(prefix)
    expect(clusterKeys.byQuadrant("q", true).slice(0, prefix.length)).toEqual(prefix)
    expect(clusterKeys.bento(8, true).slice(0, prefix.length)).toEqual(prefix)
  })
})
