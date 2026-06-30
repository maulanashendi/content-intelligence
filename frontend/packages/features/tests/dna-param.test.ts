import { describe, test, expect } from "bun:test"
import { parseDnaParam } from "../src/morning/dna-param.js"

describe("parseDnaParam", () => {
  test("no param → true (default ON)", () => {
    expect(parseDnaParam(new URLSearchParams())).toBe(true)
  })

  test("?dna=off → false", () => {
    expect(parseDnaParam(new URLSearchParams("dna=off"))).toBe(false)
  })

  test("?dna=on → true", () => {
    expect(parseDnaParam(new URLSearchParams("dna=on"))).toBe(true)
  })

  test("?dna=anything → true (only 'off' disables)", () => {
    expect(parseDnaParam(new URLSearchParams("dna=anything"))).toBe(true)
    expect(parseDnaParam(new URLSearchParams("dna=false"))).toBe(true)
    expect(parseDnaParam(new URLSearchParams("dna=0"))).toBe(true)
  })
})
