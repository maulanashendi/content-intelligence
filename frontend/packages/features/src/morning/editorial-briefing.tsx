import type { ClusterSummary } from "@ei-fe/api"

interface EditorialBriefingProps {
  clusters: ClusterSummary[]
}

function now(): string {
  return new Date().toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }) + " wib"
}

export function EditorialBriefing({ clusters }: EditorialBriefingProps) {
  const topVelocity = [...clusters].sort((a, b) => (b.trend_velocity ?? 0) - (a.trend_velocity ?? 0)).slice(0, 3)
  const highCompetitor = clusters.filter((c) => (c.competitor_count ?? 0) >= 5).slice(0, 3)
  const underperformed = clusters.filter((c) => c.underperformed).slice(0, 2)
  const stale = clusters.filter((c) => (c.last_internal_days_ago ?? 0) > 7 && !c.tempo_covered).slice(0, 2)

  return (
    <div className="card briefing" style={{ margin: "0 28px 0" }}>
      <div className="card-head">
        <span className="card-title">
          <span className="ai-dot" />
          AI editorial briefing
        </span>
        <span className="card-meta">generated {now()} · berdasarkan data terkini</span>
      </div>
      <div className="briefing-body">
        {clusters.length === 0 ? (
          <p
            style={{
              color: "var(--fg-faint)",
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              textAlign: "center",
              padding: "16px 0",
            }}
          >
            tidak ada
          </p>
        ) : (
          <>
            <p className="briefing-greeting">
              <span className="serif">Selamat pagi, Redaksi.</span>{" "}
              Berikut kondisi siklus berita dari {clusters.length} kluster aktif hari ini — dan di mana Tempo masih punya ruang.
            </p>

            {topVelocity.length > 0 && (
              <div className="briefing-section">
                <div className="briefing-h">Paling Panas Saat Ini</div>
                <ul className="briefing-list">
                  {topVelocity.map((c) => (
                    <li key={c.id}>
                      <strong>{c.label}</strong> mendominasi tren (velocity {c.trend_velocity?.toFixed(2)}).{" "}
                      {c.member_count} artikel dari {c.competitor_count ?? "—"} outlet kompetitor —{" "}
                      {(c.competitor_count ?? 0) >= 5
                        ? "cerita sudah ramai, butuh sudut baru."
                        : "masih ada ruang untuk investigasi."}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {highCompetitor.length > 0 && (
              <div className="briefing-section">
                <div className="briefing-h">Kompetitor Aktif — Peluang Worth Writing</div>
                <ul className="briefing-list">
                  {highCompetitor.map((c) => (
                    <li key={c.id}>
                      <strong>{c.label}</strong> — {c.competitor_count} sumber kompetitor,{" "}
                      {c.trend_match_count ?? 0} sinyal trend.{" "}
                      {!c.tempo_covered ? (
                        <em>Tempo belum masuk — lane terbuka.</em>
                      ) : (
                        "Tempo sudah menulis topik ini."
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {stale.length > 0 && (
              <div className="briefing-section">
                <div className="briefing-h">Di Mana Tempo Punya Lane</div>
                <ul className="briefing-list">
                  {stale.map((c) => (
                    <li key={c.id}>
                      <strong>{c.label}</strong> — terakhir ditulis {c.last_internal_days_ago} hari lalu.{" "}
                      <em>
                        {(c.competitor_count ?? 0) < 5
                          ? "Volume kompetitor masih rendah, momentum tersedia."
                          : "Kompetitor aktif — pertimbangkan sudut analisis baru."}
                      </em>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {underperformed.length > 0 && (
              <div className="briefing-section">
                <div className="briefing-h">Kandidat Rewrite</div>
                <ul className="briefing-list">
                  {underperformed.map((c) => (
                    <li key={c.id}>
                      <strong>{c.label}</strong> — artikel Tempo underperformed di GSC.{" "}
                      Pertimbangkan rewrite dengan angle baru.
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="briefing-foot">
              <span className="mono faint" style={{ fontSize: 10.5 }}>
                ringkasan berdasarkan {clusters.length} kluster aktif · {clusters.reduce((s, c) => s + (c.member_count ?? 0), 0)} artikel total
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
