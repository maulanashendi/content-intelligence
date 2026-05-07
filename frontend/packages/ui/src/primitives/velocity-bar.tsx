interface VelocityBarProps {
  velocity: number | null
  max?: number
}

export function VelocityBar({ velocity, max = 100 }: VelocityBarProps) {
  if (velocity == null) {
    return (
      <div className="score-split">
        <span className="score-num muted">—</span>
      </div>
    )
  }
  const pct = Math.min(100, Math.max(0, (velocity / max) * 100))
  return (
    <div className="score-split">
      <span className="score-num">{velocity.toFixed(1)}</span>
      <div className="score-bar">
        <span className="seg-p" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
