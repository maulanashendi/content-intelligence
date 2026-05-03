import { useTrendSignals } from "@ei-fe/api"
import type { TrendSignal } from "@ei-fe/api"
import { formatTime } from "@ei-fe/core"

type Flag = "rising" | "new" | "fading" | null

function getFlag(score: number | null, rank: number): Flag {
  if (score === null) return null
  if (rank <= 2 && score >= 80) return "rising"
  if (rank <= 4 && score >= 60) return "new"
  if (score < 40) return "fading"
  return null
}

const FLAG_CLASS: Record<NonNullable<Flag>, string> = {
  rising: "badge badge-ok",
  new: "badge badge-recommended",
  fading: "badge badge-saturated",
}

const FLAG_LABEL: Record<NonNullable<Flag>, string> = {
  rising: "↑ rising",
  new: "new",
  fading: "↓ fading",
}

function formatCaptured(iso: string): string {
  return formatTime(iso) + " wib"
}

function TrendRow({ signal, rank }: { signal: TrendSignal; rank: number }) {
  const flag = getFlag(signal.interest_score, rank)
  return (
    <div className="kw-row">
      <span className="kw-rank">{String(rank).padStart(2, "0")}</span>
      <div>
        <div className="kw-name">{signal.keyword}</div>
        <div className="kw-meta">
          interest {signal.interest_score ?? "—"} · {signal.article_count} art
        </div>
      </div>
      <div>
        {flag ? (
          <span className={FLAG_CLASS[flag]}>{FLAG_LABEL[flag]}</span>
        ) : (
          <span />
        )}
      </div>
      <span className="kw-score">{signal.interest_score ?? "—"}</span>
    </div>
  )
}

export function TrendSignalCard({ sticky = false }: { sticky?: boolean }) {
  const { data, isLoading, isError } = useTrendSignals(10)

  const captured = data?.[0] ? formatCaptured(data[0].captured_at) : "—"

  return (
    <div className="card" style={{ height: "fit-content", ...(sticky && { position: "sticky", top: 20 }) }}>
      <div className="card-head">
        <span className="card-title">Trend signals</span>
        <span className="card-meta">{captured} · Google Trends ID</span>
      </div>
      <div>
        {isLoading && (
          <div style={{ padding: "16px 20px", color: "var(--text-muted, #888)", fontSize: 13 }}>
            Memuat trend…
          </div>
        )}
        {isError && (
          <div style={{ padding: "16px 20px", color: "var(--text-muted, #888)", fontSize: 13 }}>
            Gagal memuat trend signals.
          </div>
        )}
        {!isLoading && !isError && data?.length === 0 && (
          <div style={{ padding: "16px 20px", color: "var(--text-muted, #888)", fontSize: 13 }}>
            Belum ada data trend.
          </div>
        )}
        {data?.map((s, i) => (
          <TrendRow key={s.id} signal={s} rank={i + 1} />
        ))}
      </div>
    </div>
  )
}
