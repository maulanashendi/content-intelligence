import { scaleLinear } from "d3"

export interface SparklineDims {
  width: number
  height: number
  pad: number
}

export interface SparklineModel {
  linePath: string
  areaPath: string
  lastX: number
  lastY: number
}

export function buildSparkline(values: number[], dims: SparklineDims): SparklineModel {
  if (values.length === 0) {
    return { linePath: "", areaPath: "", lastX: 0, lastY: 0 }
  }

  const { width, height, pad } = dims
  const max = Math.max(...values)
  const min = Math.min(...values)
  const x = scaleLinear()
    .domain([0, Math.max(1, values.length - 1)])
    .range([pad, width - pad])
  const y = scaleLinear()
    .domain([min, max === min ? min + 1 : max])
    .range([height - pad, pad])

  const points = values.map((v, i) => [x(i), y(v)] as const)
  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(2)} ${p[1].toFixed(2)}`)
    .join(" ")
  const baseline = height - pad
  // non-null: values.length === 0 already returned above, so points has ≥1 element
  const first = points[0]!
  const last = points[points.length - 1]!
  const areaPath = `${linePath} L${last[0].toFixed(2)} ${baseline.toFixed(2)} L${first[0].toFixed(2)} ${baseline.toFixed(2)} Z`

  return { linePath, areaPath, lastX: last[0], lastY: last[1] }
}
