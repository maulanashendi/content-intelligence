interface SignalBadgeProps {
  tempoCovered: boolean | null | undefined
  underperformed?: boolean | null
  className?: string
}

export function SignalBadge({ tempoCovered, underperformed, className }: SignalBadgeProps) {
  if (tempoCovered) {
    const cls = `badge badge-ok${className ? " " + className : ""}`
    return <span className={cls}>sudah ditulis</span>
  }
  if (underperformed) {
    const cls = `badge badge-warn${className ? " " + className : ""}`
    return <span className={cls}>underperformed</span>
  }
  const cls = `badge badge-active${className ? " " + className : ""}`
  return <span className={cls}>belum ditulis</span>
}
