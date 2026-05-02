import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { useSources, useDeleteSource, useToggleSource, useTriggerIngestEmbed, useTriggerClusterLabelScore, usePipelineStatus } from "@ei-fe/api"
import type { PipelineStatus } from "@ei-fe/api"
import { formatDateTime } from "@ei-fe/core"
import { LoadingState, ErrorState, EmptyState } from "@ei-fe/ui"

const STATUS_DOT: Record<string, string> = {
  active: "dot-ok",
  error: "dot-bad",
  blocked: "dot-warn",
}

const TYPE_BADGE: Record<string, string> = {
  rss: "badge badge-active",
  internal: "badge badge-watching",
}

const TYPE_LABEL: Record<string, string> = {
  rss: "rss",
  internal: "internal",
}

type GroupKey = "ingest_embed" | "cluster_label_score"

const GROUPS: { key: GroupKey; label: string }[] = [
  { key: "ingest_embed", label: "Ingest + Embed" },
  { key: "cluster_label_score", label: "Cluster + Label + Score" },
]

// How long to keep a button in "waiting for daemon" state after triggering
const GRACE_MS = 30_000

export function SourcesRoute() {
  const { data: sources, isLoading, isError, error, refetch } = useSources()
  const deleteMutation = useDeleteSource()
  const toggleMutation = useToggleSource()
  const triggerIngestEmbed = useTriggerIngestEmbed()
  const triggerClusterLabelScore = useTriggerClusterLabelScore()

  const [watching, setWatching] = useState(false)
  const [pipelineMsg, setPipelineMsg] = useState<string | null>(null)
  // group → timestamp when user triggered it (for grace period)
  const triggeredRef = useRef<Partial<Record<GroupKey, number>>>({})
  // previous poll result for transition detection
  const prevStatusRef = useRef<PipelineStatus | null>(null)

  const { data: pipelineStatus } = usePipelineStatus(watching ? 10_000 : false)

  // Bootstrap: start watching if any group is already running when page loads
  useEffect(() => {
    if (!pipelineStatus || prevStatusRef.current !== null) return
    if (pipelineStatus.ingest_embed !== null || pipelineStatus.cluster_label_score !== null) {
      setWatching(true)
    }
  }, [pipelineStatus])

  // Detect running→idle transitions to show "selesai" or "daemon tidak aktif"
  useEffect(() => {
    if (!pipelineStatus) return
    const prev = prevStatusRef.current
    prevStatusRef.current = pipelineStatus

    if (prev === null) return

    const now = Date.now()
    for (const { key, label } of GROUPS) {
      const wasRunning = prev[key] !== null
      const isRunning = pipelineStatus[key] !== null
      const triggeredAt = triggeredRef.current[key]

      if (wasRunning && !isRunning) {
        setPipelineMsg(`Pipeline ${label} selesai.`)
        delete triggeredRef.current[key]
      } else if (!isRunning && triggeredAt && now - triggeredAt > GRACE_MS) {
        setPipelineMsg(`Pipeline ${label} tidak merespons — pastikan daemon berjalan.`)
        delete triggeredRef.current[key]
      }
    }

    const anyRunning = pipelineStatus.ingest_embed !== null || pipelineStatus.cluster_label_score !== null
    const anyPending = Object.keys(triggeredRef.current).length > 0
    if (!anyRunning && !anyPending) setWatching(false)
  }, [pipelineStatus])

  function isGroupBusy(key: GroupKey): boolean {
    if (pipelineStatus?.[key] !== null && pipelineStatus?.[key] !== undefined) return true
    const triggeredAt = triggeredRef.current[key]
    return !!triggeredAt && Date.now() - triggeredAt < GRACE_MS
  }

  function groupButtonLabel(key: GroupKey, defaultLabel: string): string {
    if (pipelineStatus?.[key] !== null && pipelineStatus?.[key] !== undefined) return "⏳ Sedang berjalan…"
    const triggeredAt = triggeredRef.current[key]
    if (triggeredAt && Date.now() - triggeredAt < GRACE_MS) return "⏳ Menunggu daemon…"
    return `▶ ${defaultLabel}`
  }

  function handleTrigger(
    mutation: typeof triggerIngestEmbed,
    key: GroupKey,
    label: string,
  ) {
    setPipelineMsg(null)
    mutation.mutate(undefined, {
      onSuccess: (data) => {
        if (data.notified) {
          triggeredRef.current[key] = Date.now()
          setWatching(true)
          setPipelineMsg(`Pipeline ${label} dipicu — menunggu konfirmasi…`)
        } else {
          setPipelineMsg(`Trigger dikirim tapi daemon tidak merespons — coba lagi.`)
        }
      },
      onError: (err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err)
        if (msg.startsWith("Pipeline group")) {
          // Group already locked — start watching so we can report when it finishes
          setWatching(true)
          setPipelineMsg(msg)
        } else {
          setPipelineMsg(`Gagal memicu pipeline ${label}.`)
        }
      },
    })
  }

  if (isLoading) return <LoadingState variant="table" />
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />

  const list = sources ?? []
  const totalArticles = list.reduce((sum, s) => sum + s.article_count_24h, 0)
  const activeCount = list.filter((s) => s.status === "active").length
  const problemCount = list.filter((s) => s.status !== "active" && s.status !== null).length

  function handleDelete(id: string, name: string) {
    if (!confirm(`Hapus sumber "${name}"? Tindakan ini tidak dapat dibatalkan.`)) return
    deleteMutation.mutate(id)
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Content <span className="serif">Sources</span></h1>
          <p className="page-sub">Sumber konten yang diingest pipeline setiap hari</p>
        </div>
        <div className="page-actions">
          <Link to="/sources/rss" className="btn">+ RSS Feed</Link>
        </div>
      </div>

      <div className="page-body">
        <div className="card" style={{ marginBottom: 16, padding: "14px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span className="card-title" style={{ marginRight: 4 }}>Pipeline Manual</span>
            <button
              className="btn"
              disabled={isGroupBusy("ingest_embed") || triggerIngestEmbed.isPending}
              onClick={() => handleTrigger(triggerIngestEmbed, "ingest_embed", "Ingest + Embed")}
              style={{ fontSize: 12 }}
            >
              {groupButtonLabel("ingest_embed", "Ingest + Embed")}
            </button>
            <button
              className="btn"
              disabled={isGroupBusy("cluster_label_score") || triggerClusterLabelScore.isPending}
              onClick={() => handleTrigger(triggerClusterLabelScore, "cluster_label_score", "Cluster + Label + Score")}
              style={{ fontSize: 12 }}
            >
              {groupButtonLabel("cluster_label_score", "Cluster + Label + Score")}
            </button>
            {pipelineMsg && (
              <span className="faint" style={{ fontSize: 12, marginLeft: 4 }}>{pipelineMsg}</span>
            )}
          </div>
        </div>

        <div className="grid grid-4" style={{ marginBottom: 20 }}>
          <div className="kpi">
            <div className="kpi-label">Total Sumber</div>
            <div className="kpi-value">{list.length}</div>
          </div>
          <div className="kpi">
            <div className="kpi-label">Aktif</div>
            <div className="kpi-value">{activeCount}</div>
          </div>
          <div className="kpi">
            <div className="kpi-label">Bermasalah</div>
            <div className="kpi-value" style={{ color: "var(--bad)" }}>{problemCount}</div>
          </div>
          <div className="kpi">
            <div className="kpi-label">Artikel (24j)</div>
            <div className="kpi-value">{totalArticles.toLocaleString("id-ID")}</div>
          </div>
        </div>

        {list.length === 0 ? (
          <EmptyState title="Belum ada sumber" description="Tambahkan RSS feed pertama Anda." />
        ) : (
          <div className="card">
            <div className="card-head">
              <span className="card-title">Semua sumber</span>
              <span className="card-meta">{list.length} terdaftar</span>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Nama</th>
                  <th>Tipe</th>
                  <th>URL</th>
                  <th>Terakhir fetch</th>
                  <th className="right">Artikel (24j)</th>
                  <th>Aktif</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {list.map((s) => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 500 }}>{s.name || s.url}</td>
                    <td><span className={TYPE_BADGE[s.source_type] ?? "badge"}>{TYPE_LABEL[s.source_type] ?? s.source_type}</span></td>
                    <td className="mono faint" style={{ fontSize: 11.5, maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.url}</td>
                    <td className="mono faint" style={{ fontSize: 11.5 }}>
                      {formatDateTime(s.last_fetched_at)}
                    </td>
                    <td className="num right">{s.article_count_24h}</td>
                    <td>
                      <input
                        type="checkbox"
                        checked={s.is_enabled}
                        disabled={toggleMutation.isPending}
                        onChange={() => toggleMutation.mutate({ id: s.id, is_enabled: !s.is_enabled })}
                        style={{ cursor: "pointer", accentColor: "var(--accent)" }}
                      />
                    </td>
                    <td>
                      {s.status && (
                        <span className={`dot-status ${STATUS_DOT[s.status] ?? "dot-warn"}`} />
                      )}
                    </td>
                    <td>
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 11, padding: "2px 8px", color: "var(--bad)" }}
                        disabled={deleteMutation.isPending}
                        onClick={() => handleDelete(s.id, s.name || s.url)}
                      >
                        Hapus
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
