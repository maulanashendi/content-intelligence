// Keyword ranking page

function KeywordsPage() {
  const { KEYWORDS, BUCKETS } = window.CIData;
  return (
    <div className="page-body" style={{ maxWidth: 1100 }}>
      <div className="filterbar" style={{ marginBottom: 18 }}>
        <button className="chip active">All <span className="num">{KEYWORDS.length}</span></button>
        <button className="chip">Rising <span className="num">3</span></button>
        <button className="chip">New <span className="num">3</span></button>
        <button className="chip">Fading <span className="num">1</span></button>
        <span className="spacer" />
        <div className="search"><Icon name="search" size={12}/><input placeholder="search keyword…" /></div>
      </div>

      <div className="card">
        <div className="card-head">
          <span className="card-title">Keyword ranking · 7d window</span>
          <span className="card-meta">composite = rss 50% + trend 30% + gsc 20%</span>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>Keyword</th>
              <th>Status</th>
              <th className="num">RSS freq</th>
              <th className="num">Google Trends</th>
              <th className="num">GSC impr.</th>
              <th className="num">Composite</th>
              <th>Linked buckets</th>
            </tr>
          </thead>
          <tbody>
            {KEYWORDS.map((k, i) => (
              <tr key={k.kw} className="row-clickable">
                <td className="num faint">{String(i + 1).padStart(2, "0")}</td>
                <td><span style={{ fontWeight: 500 }}>{k.kw}</span></td>
                <td>
                  {k.flag === "rising" && <span className="badge badge-rising"><Icon name="arrowUp" size={10}/>rising</span>}
                  {k.flag === "new" && <span className="badge badge-new">new</span>}
                  {k.flag === "fading" && <span className="badge badge-fading"><Icon name="arrowDown" size={10}/>fading</span>}
                  {!k.flag && <span className="faint mono" style={{ fontSize: 11 }}>—</span>}
                </td>
                <td className="num">{k.rss}</td>
                <td className="num">{k.trend ?? <span className="faint">—</span>}</td>
                <td className="num">{k.gsc ?? <span className="faint">—</span>}</td>
                <td className="num" style={{ fontWeight: 600 }}>{k.comp}</td>
                <td>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {k.buckets.map(bid => {
                      const b = BUCKETS.find(x => x.id === bid);
                      if (!b) return null;
                      return <span key={bid} className="ent">#{String(bid).padStart(4, "0")} {b.label.split(" / ")[0]}</span>;
                    })}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

window.KeywordsPage = KeywordsPage;
