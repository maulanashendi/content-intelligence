interface SignalBadgeProps {
  tempoCovered: boolean | null | undefined
  lastInternalDaysAgo?: number | null
  underperformed?: boolean | null
  className?: string
}

export function SignalBadge({ tempoCovered, lastInternalDaysAgo, underperformed, className }: SignalBadgeProps) {
  if (tempoCovered) {
    const cls = `badge badge-ok${className ? " " + className : ""}`
    const label = lastInternalDaysAgo != null
      ? `sudah ditulis ${lastInternalDaysAgo} hari lalu`
      : "sudah ditulis"
    return <span className={cls}>{label}</span>
  }
  if (underperformed) {
    const cls = `badge badge-warn${className ? " " + className : ""}`
    return <span className={cls}>underperformed</span>
  }
  const cls = `badge badge-active${className ? " " + className : ""}`
  return <span className={cls}>belum ditulis</span>
}
