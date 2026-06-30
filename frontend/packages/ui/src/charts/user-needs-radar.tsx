import { radarPoints } from "./radar-points.js"
import type { UserNeedDatum as Need } from "./radar-points.js"

// viewBox carries generous horizontal padding so the longest labels ("Perspektif",
// "Inspirasi") stay fully inside the box and never bleed into the bars column beside it.
// cx=190 (centered in 380), cy=145, r=96; right label end ≈356 < 380, left label ≈29 > 0.
const VB = { w: 380, h: 290, cx: 190, cy: 145, r: 96 }

const ANIMATION_ID = "ei-radar-draw"

export function UserNeedsRadar({ needs }: { needs: Need[] }) {
  const values = needs.map((n) => n.value)
  const ring = (f: number) =>
    radarPoints(needs.map(() => f * 100), VB.cx, VB.cy, VB.r)
      .map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`)
      .join(" ")
  const dataPts = radarPoints(values, VB.cx, VB.cy, VB.r)
  const dom = needs.map((n) => n.value >= 70)
  const n = needs.length
  const dataPolyPts = dataPts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")

  const dominantNeeds = needs.filter((nd) => nd.value >= 70)
  const ariaLabel = `Radar kebutuhan pembaca. Dominan: ${
    dominantNeeds.length > 0
      ? dominantNeeds.map((nd) => `${nd.label} ${nd.value}`).join(", ")
      : "tidak ada"
  }.`

  return (
    <>
      {/* Scoped keyframe: draw-in from center on mount. No-ops under prefers-reduced-motion. */}
      <style>{`
        @keyframes ${ANIMATION_ID} {
          from { transform: scale(0.1); opacity: 0; }
          to   { transform: scale(1);   opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .${ANIMATION_ID} { animation: none !important; opacity: 1 !important; transform: scale(1) !important; }
        }
        .${ANIMATION_ID} {
          transform-origin: ${VB.cx}px ${VB.cy}px;
          animation: ${ANIMATION_ID} 450ms ease-out both;
        }
      `}</style>

      <svg
        viewBox={`0 0 ${VB.w} ${VB.h}`}
        role="img"
        aria-label={ariaLabel}
        style={{ display: "block", width: "100%", maxWidth: "300px", height: "auto" }}
      >
        {/* Concentric rings — 0.25/0.5/0.75 thin, outer (1.0) slightly stronger */}
        {[0.25, 0.5, 0.75].map((f) => (
          <polygon key={f} points={ring(f)} fill="none" stroke="var(--line)" strokeWidth="0.75" />
        ))}
        <polygon points={ring(1)} fill="none" stroke="var(--line-strong)" strokeWidth="1.25" />

        {/* Spokes */}
        {dataPts.map((_, i) => {
          const spoke = radarPoints(needs.map((_, j) => (j === i ? 100 : 0)), VB.cx, VB.cy, VB.r)[i]
          return (
            <line
              key={i}
              x1={VB.cx} y1={VB.cy}
              x2={spoke[0]} y2={spoke[1]}
              stroke="var(--line)"
              strokeWidth="0.75"
            />
          )
        })}

        {/* Data polygon + dots — animated draw-in group */}
        <g className={ANIMATION_ID}>
          <polygon
            points={dataPolyPts}
            fill="oklch(0.55 0.15 262 / 0.13)"
            stroke="var(--accent)"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          {dataPts.map((p, i) => (
            <g key={i}>
              {/* Soft halo behind dominant dots */}
              {dom[i] && (
                <circle
                  cx={p[0]} cy={p[1]}
                  r={9}
                  fill="oklch(0.45 0.18 285 / 0.18)"
                />
              )}
              <circle
                cx={p[0]} cy={p[1]}
                r={dom[i] ? 4.5 : 2.6}
                fill={dom[i] ? "oklch(0.45 0.18 285)" : "var(--accent)"}
              />
            </g>
          ))}
        </g>

        {/* Axis labels — SANS, not mono */}
        {needs.map((nd, i) => {
          const angle = (-90 + i * (360 / n)) * (Math.PI / 180)
          const lx = VB.cx + (VB.r + 32) * Math.cos(angle)
          const ly = VB.cy + (VB.r + 32) * Math.sin(angle)
          const anchor = lx < VB.cx - 10 ? "end" : lx > VB.cx + 10 ? "start" : "middle"
          return (
            <text
              key={nd.key}
              x={lx}
              y={ly + 4}
              textAnchor={anchor}
              fontFamily="var(--font-sans)"
              fontSize="10.5"
              fill={dom[i] ? "var(--accent-fg)" : "var(--fg-muted)"}
              fontWeight={dom[i] ? 600 : 400}
            >
              {nd.label}
            </text>
          )
        })}
      </svg>
    </>
  )
}
