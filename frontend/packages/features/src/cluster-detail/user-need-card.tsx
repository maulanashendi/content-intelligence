import type { ClusterDetail } from "@ei-fe/api"
import { UserNeedsRadar, UserNeedsBars } from "@ei-fe/ui"
import { distributionToNeeds } from "./user-need-data.js"

export function UserNeedCard({ cluster }: { cluster: ClusterDetail }) {
  const needs = distributionToNeeds(cluster.user_need_distribution)
  const reps = cluster.user_need_reps_tagged ?? 0
  if (needs.length === 0) return null

  return (
    <div
      className="overflow-hidden border rounded-[var(--radius-lg)]"
      style={{ background: "var(--bg-elev)", borderColor: "var(--line)" }}
    >
      <div
        className="flex items-center gap-[10px] px-[14px] py-[12px] border-b"
        style={{ borderColor: "var(--line)" }}
      >
        <span
          className="text-[12px] font-semibold uppercase tracking-[0.01em]"
          style={{ color: "var(--fg-muted)" }}
        >
          Kebutuhan Pembaca
        </span>
        <span
          className="ml-auto text-[11.5px]"
          style={{ color: "var(--fg-faint)", fontFamily: "var(--font-mono)" }}
        >
          {reps < 3 ? "indikatif · " : ""}berdasarkan {reps} artikel
        </span>
      </div>
      <div className="flex flex-col gap-3 p-[14px]">
        <UserNeedsRadar needs={needs} />
        <UserNeedsBars needs={needs} />
      </div>
    </div>
  )
}
