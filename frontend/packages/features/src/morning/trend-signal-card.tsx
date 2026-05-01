import { formatTime } from "@ei-fe/core"

/* Dummy data matching TrendSignal schema: keyword, interest_score, region, captured_at */
const TREND_SIGNALS = [
  { keyword: "Kenaikan Harga BBM", interest_score: 94, captured_at: "2025-04-30T06:00:00Z", article_count: 23 },
  { keyword: "Sidang MK Pilkada", interest_score: 87, captured_at: "2025-04-30T06:00:00Z", article_count: 18 },
  { keyword: "Korupsi Dana Desa", interest_score: 81, captured_at: "2025-04-30T06:00:00Z", article_count: 31 },
  { keyword: "PPRT Pengesahan", interest_score: 76, captured_at: "2025-04-30T06:00:00Z", article_count: 12 },
  { keyword: "Prabowo Xi Jinping", interest_score: 68, captured_at: "2025-04-30T06:00:00Z", article_count: 9 },
  { keyword: "BPJS Iuran Baru", interest_score: 61, captured_at: "2025-04-30T06:00:00Z", article_count: 15 },
  { keyword: "Karhutla Kalbar", interest_score: 55, captured_at: "2025-04-30T06:00:00Z", article_count: 7 },
  { keyword: "Startup PHK", interest_score: 48, captured_at: "2025-04-30T06:00:00Z", article_count: 20 },
  { keyword: "Rupiah Melemah", interest_score: 41, captured_at: "2025-04-30T06:00:00Z", article_count: 11 },
  { keyword: "CPNS 2025", interest_score: 34, captured_at: "2025-04-30T06:00:00Z", article_count: 8 },
]

type Flag = "rising" | "new" | "fading" | null

function getFlag(score: number, rank: number): Flag {
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

export function TrendSignalCard() {
  const captured = TREND_SIGNALS[0] ? formatCaptured(TREND_SIGNALS[0].captured_at) : "—"

  return (
    <div className="card" style={{ height: "fit-content" }}>
      <div className="card-head">
        <span className="card-title">Trend signals</span>
        <span className="card-meta">{captured} · Google Trends ID</span>
      </div>
      <div>
        {TREND_SIGNALS.map((s, i) => {
          const flag = getFlag(s.interest_score, i + 1)
          return (
            <div key={s.keyword} className="kw-row">
              <span className="kw-rank">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <div className="kw-name">{s.keyword}</div>
                <div className="kw-meta">
                  interest {s.interest_score} · {s.article_count} art
                </div>
              </div>
              <div>
                {flag ? (
                  <span className={FLAG_CLASS[flag]}>{FLAG_LABEL[flag]}</span>
                ) : (
                  <span />
                )}
              </div>
              <span className="kw-score">{s.interest_score}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
