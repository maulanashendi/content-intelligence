import { Link } from "react-router-dom"
import type { ClusterDetail, ClusterSummary } from "@ei-fe/api"
import { cn } from "@ei-fe/ui"

interface RelatedClustersCardProps {
  cluster: ClusterDetail
}

function ClusterLink({ c }: { c: ClusterSummary }) {
  return (
    <Link
      to={`/clusters/${c.id}`}
      className={cn(
        "flex items-center justify-between gap-2 rounded px-2 py-1.5",
        "text-[13px] leading-snug no-underline",
        "hover:bg-[var(--surface-hover)] transition-colors"
      )}
    >
      <span style={{ color: "var(--fg)" }}>{c.label ?? "—"}</span>
      {c.member_count != null && (
        <span
          className="shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium"
          style={{ background: "var(--surface-2)", color: "var(--fg-muted)" }}
        >
          {c.member_count}
        </span>
      )}
    </Link>
  )
}

function Section({ title, items }: { title: string; items: ClusterSummary[] }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className="px-2 text-[11px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--fg-muted)" }}
      >
        {title}
      </span>
      {items.map((c) => (
        <ClusterLink key={c.id} c={c} />
      ))}
    </div>
  )
}

export function RelatedClustersCard({ cluster }: RelatedClustersCardProps) {
  const { parent_cluster, sibling_clusters, sub_clusters } = cluster

  const hasSiblings = sibling_clusters && sibling_clusters.length > 0
  const hasSubs = sub_clusters && sub_clusters.length > 0

  if (!parent_cluster && !hasSiblings && !hasSubs) return null

  return (
    <div
      className="flex flex-col gap-3 rounded-lg p-3"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <span
        className="text-[11px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--fg-muted)" }}
      >
        Cluster Terkait
      </span>

      {parent_cluster && (
        <Section title="Cluster Induk" items={[parent_cluster]} />
      )}

      {hasSiblings && (
        <Section title="Cluster Sodara" items={sibling_clusters!} />
      )}

      {hasSubs && (
        <Section title="Sub-cluster" items={sub_clusters!} />
      )}
    </div>
  )
}
