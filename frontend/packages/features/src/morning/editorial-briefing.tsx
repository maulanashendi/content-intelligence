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
  const trending = clusters.filter((c) => c.recommendation === "trending")
  const worthWriting = clusters.filter((c) => c.recommendation === "worth_writing")
  const topVelocity = [...clusters].sort((a, b) => (b.trend_velocity ?? 0) - (a.trend_velocity ?? 0)).slice(0, 3)
  const highNovelty = worthWriting.filter((c) => (c.novelty_score ?? 0) > 0.6).slice(0, 3)
  const lowCoverage = worthWriting.filter((c) => (c.coverage_score ?? 1) < 0.35).slice(0, 2)

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
                  <strong>{c.label}</strong> mendominasi tren (velocity {c.trend_velocity?.toFixed(1)}).{" "}
                  {c.member_count} artikel dari berbagai outlet —{" "}
                  {(c.coverage_score ?? 0) > 0.6
                    ? "cerita sudah padat, butuh sudut baru."
                    : "masih ada ruang untuk investigasi."}
                </li>
              ))}
            </ul>
          </div>
        )}

        {highNovelty.length > 0 && (
          <div className="briefing-section">
            <div className="briefing-h">Nilai Novelty Tinggi — Worth Writing</div>
            <ul className="briefing-list">
              {highNovelty.map((c) => (
                <li key={c.id}>
                  <strong>{c.label}</strong> — novelty{" "}
                  {c.novelty_score != null ? Math.round(c.novelty_score * 100) : "—"}%,{" "}
                  coverage {c.coverage_score != null ? Math.round(c.coverage_score * 100) : "—"}%.{" "}
                  {(c.coverage_score ?? 1) < 0.4 ? (
                    <em>Belum banyak yang menulis — lane terbuka.</em>
                  ) : (
                    "Kompetitor sudah masuk tapi masih tipis."
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {lowCoverage.length > 0 && (
          <div className="briefing-section">
            <div className="briefing-h">Di Mana Tempo Punya Lane</div>
            <ul className="briefing-list">
              {lowCoverage.map((c) => (
                <li key={c.id}>
                  <strong>{c.label}</strong> — coverage hanya{" "}
                  {c.coverage_score != null ? Math.round(c.coverage_score * 100) : "—"}%.{" "}
                  <em>
                    {c.member_count != null && c.member_count < 10
                      ? "Volume masih rendah, kompetitor belum masuk penuh."
                      : "Ada celah sudut analisis yang belum ditulis."}
                  </em>
                </li>
              ))}
            </ul>
          </div>
        )}

        {trending.length > 0 && (
          <div className="briefing-section">
            <div className="briefing-h">Yang Perlu Dipantau</div>
            <ul className="briefing-list">
              {trending.map((c) => (
                <li key={c.id}>
                  <strong>{c.label}</strong> — sedang trending dengan velocity {c.trend_velocity?.toFixed(1)}.
                  {" "}Pantau pergerakan 6 jam ke depan sebelum memutuskan sudut tulisan.
                </li>
              ))}
              {clusters.filter((c) => (c.coverage_score ?? 0) > 0.8).slice(0, 1).map((c) => (
                <li key={c.id + "-warn"}>
                  <strong>{c.label}</strong> coverage sudah {c.coverage_score != null ? Math.round(c.coverage_score * 100) : "—"}% — pertimbangkan deprioritisasi.
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
      </div>
    </div>
  )
}
