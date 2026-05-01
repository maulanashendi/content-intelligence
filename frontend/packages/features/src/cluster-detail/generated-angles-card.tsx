import type { ClusterDetail } from "@ei-fe/api"

interface GeneratedAnglesCardProps {
  cluster: ClusterDetail
}

interface Angle {
  headline: string
  insight: string
  openAngle: string
  competitors: { name: string; note: string }[]
}

function buildAngles(cluster: ClusterDetail): Angle[] {
  const sources = [...new Set(cluster.members.map((m) => m.source_name))]
  const label = cluster.label ?? "topik ini"
  const topSource = cluster.members[0]?.source_name ?? "Kompas"
  const secondSource = cluster.members[1]?.source_name ?? "Detik"
  const thirdSource = cluster.members[2]?.source_name ?? "CNN Indonesia"
  const highRelevance = cluster.members.filter((m) => (m.relevance_score ?? 0) > 0.85)
  const coverage = cluster.coverage_score != null ? Math.round(cluster.coverage_score * 100) : 0

  return [
    {
      headline: `Dampak jangka panjang ${label} terhadap kelompok rentan`,
      insight: `Coverage saat ini ${coverage}% — mayoritas outlet hanya menyentuh permukaan berita. Belum ada yang mengangkat perspektif masyarakat terdampak secara mendalam.`,
      openAngle: `Investigasi lapangan ke komunitas terdampak langsung.`,
      competitors: [
        { name: topSource, note: "breaking news saja, tanpa analisis dampak" },
        { name: secondSource, note: "kutip pejabat, tidak ada warga yang diwawancarai" },
        { name: thirdSource, note: "replikasi siaran pers, tidak ada sudut baru" },
      ],
    },
    {
      headline: `Aktor di balik ${label}: siapa yang diuntungkan?`,
      insight: `${highRelevance.length} dari ${cluster.member_count} artikel memiliki relevansi tinggi, namun tidak ada yang menelusuri rantai kepentingan di balik keputusan ini.`,
      openAngle: `Pemetaan jaringan kepentingan dan aliran dana terkait kebijakan.`,
      competitors: [
        { name: sources[0] ?? topSource, note: "fokus pada pernyataan resmi" },
        { name: sources[1] ?? secondSource, note: "hanya meliput reaksi DPR" },
      ],
    },
  ]
}

export function GeneratedAnglesCard({ cluster }: GeneratedAnglesCardProps) {
  const angles = buildAngles(cluster)

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">
          <span className="angle-tag">AI</span>
          {" "}Generated Angles · Bullet Insights
        </span>
        <span className="card-meta">{angles.length} sudut ditemukan</span>
      </div>
      <div className="ci-list">
        {angles.map((angle, i) => (
          <div key={i} className="ci-block">
            <div className="ci-block-head">
              <span
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 15,
                  fontWeight: 500,
                  lineHeight: 1.3,
                  color: "var(--fg)",
                }}
              >
                {angle.headline}
              </span>
            </div>
            <ul className="ci-bullets">
              <li>{angle.insight}</li>
              {angle.competitors.map((c) => (
                <li key={c.name}>
                  <strong>{c.name}</strong> — {c.note}
                </li>
              ))}
              <li className="ci-gap">
                <strong>Open angle:</strong> <em>{angle.openAngle}</em>
              </li>
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
