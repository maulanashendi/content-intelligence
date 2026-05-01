import type { Recommendation } from "@ei-fe/core"

const LABEL: Record<Recommendation, string> = {
  trending: "recommended",
  worth_writing: "worth writing",
  saturated: "saturated",
}

const CLASS: Record<Recommendation, string> = {
  trending: "badge badge-recommended",
  worth_writing: "badge badge-active",
  saturated: "badge badge-saturated",
}

interface RecommendationBadgeProps {
  recommendation: Recommendation | null | undefined
  className?: string
}

export function RecommendationBadge({ recommendation, className }: RecommendationBadgeProps) {
  const cls = recommendation ? CLASS[recommendation] : "badge badge-watching"
  const label = recommendation ? LABEL[recommendation] : "—"
  return (
    <span className={className ? `${cls} ${className}` : cls}>
      {label}
    </span>
  )
}
