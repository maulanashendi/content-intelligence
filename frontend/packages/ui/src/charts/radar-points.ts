export interface UserNeedDatum {
  key: string
  label: string
  value: number
}

export function radarPoints(
  values: number[],
  cx: number,
  cy: number,
  r: number,
): [number, number][] {
  const n = values.length
  return values.map((v, i) => {
    const angle = (-90 + i * (360 / n)) * (Math.PI / 180)
    const radius = (Math.min(100, Math.max(0, v)) / 100) * r
    return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]
  })
}
