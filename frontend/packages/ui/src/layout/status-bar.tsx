interface StatusBarProps {
  articleCount?: number
  clusterCount?: number
  recommendedCount?: number
  isRefetching?: boolean
}

export function StatusBar({
  articleCount = 4812,
  clusterCount = 142,
  recommendedCount = 14,
  isRefetching,
}: StatusBarProps) {
  return (
    <div className="statusbar">
      <div className="item">
        <span className="pulse" />
        <span>Pipeline aktif</span>
      </div>
      <div className="sep" />
      <div className="item">
        <strong>{articleCount.toLocaleString("id-ID")}</strong> artikel
      </div>
      <div className="sep" />
      <div className="item">
        <strong>{clusterCount}</strong> kluster
      </div>
      <div className="sep" />
      <div className="item">
        <strong>{recommendedCount}</strong> rekomendasi
      </div>
      <div className="grow" />
      {isRefetching && (
        <div className="item">
          <span style={{ color: "var(--accent)" }}>Memperbarui…</span>
        </div>
      )}
    </div>
  )
}
