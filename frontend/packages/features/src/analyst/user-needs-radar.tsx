import { radarPoints } from "./data.js"

interface Need { key: string; label: string; value: number }

const VB = { w: 320, h: 250, cx: 160, cy: 116, r: 84 }

export function UserNeedsRadar({ needs }: { needs: Need[] }) {
  const values = needs.map((n) => n.value)
  const ring = (f: number) =>
    radarPoints(needs.map(() => f * 100), VB.cx, VB.cy, VB.r)
      .map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`)
      .join(" ")
  const dataPts = radarPoints(values, VB.cx, VB.cy, VB.r)
  const dom = needs.map((n) => n.value >= 70)
  const n = needs.length

  return (
    <svg
      viewBox={`0 0 ${VB.w} ${VB.h}`}
      width="248"
      height="194"
      role="img"
      aria-label={`Radar kebutuhan pembaca. Dominan: ${needs.filter((n) => n.value >= 70).map((n) => `${n.label} ${n.value}`).join(", ") || "tidak ada"}.`}
    >
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon key={f} points={ring(f)} fill="none" stroke="var(--line)" strokeWidth="1" />
      ))}
      {dataPts.map((_, i) => {
        const spoke = radarPoints(needs.map((_, j) => (j === i ? 100 : 0)), VB.cx, VB.cy, VB.r)[i]
        return <line key={i} x1={VB.cx} y1={VB.cy} x2={spoke[0]} y2={spoke[1]} stroke="var(--line)" strokeWidth="1" />
      })}
      <polygon
        points={dataPts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")}
        fill="oklch(0.55 0.15 262 / 0.14)"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {dataPts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={dom[i] ? 4 : 2.6}
          fill={dom[i] ? "oklch(0.45 0.18 285)" : "var(--accent)"} />
      ))}
      {needs.map((nd, i) => {
        const angle = (-90 + i * (360 / n)) * (Math.PI / 180)
        const lx = VB.cx + (VB.r + 26) * Math.cos(angle)
        const ly = VB.cy + (VB.r + 26) * Math.sin(angle)
        const anchor = lx < VB.cx - 10 ? "end" : lx > VB.cx + 10 ? "start" : "middle"
        return (
          <text key={nd.key} x={lx} y={ly + 3} textAnchor={anchor}
            fontFamily="var(--font-mono)" fontSize="10"
            fill={dom[i] ? "var(--accent-fg)" : "var(--fg-muted)"}
            fontWeight={dom[i] ? 600 : 400}>
            {nd.label}
          </text>
        )
      })}
    </svg>
  )
}
