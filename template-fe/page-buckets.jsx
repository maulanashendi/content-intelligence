// Topic Buckets list page

function BucketsPage({ setSelectedBucket, setPage, vizMode }) {
  const { BUCKETS } = window.CIData;
  const [stateFilter, setStateFilter] = React.useState("all");

  const counts = {
    all: BUCKETS.length,
    RECOMMENDED: BUCKETS.filter(b => b.state === "RECOMMENDED").length,
    MATURE: BUCKETS.filter(b => b.state === "MATURE").length,
    ACTIVE: BUCKETS.filter(b => b.state === "ACTIVE").length,
    WATCHING: BUCKETS.filter(b => b.state === "WATCHING").length,
    DEPRIORITIZED: BUCKETS.filter(b => b.state === "DEPRIORITIZED").length,
    FORMING: BUCKETS.filter(b => b.state === "FORMING").length,
  };

  const visible = stateFilter === "all" ? BUCKETS : BUCKETS.filter(b => b.state === stateFilter);
  const sorted = [...visible].sort((a, b) => (b.score || 0) - (a.score || 0));

  return (
    <div className="page-body" style={{ maxWidth: 1280 }}>
      <div className="filterbar" style={{ marginBottom: 0 }}>
        {["all", "RECOMMENDED", "MATURE", "ACTIVE", "WATCHING", "DEPRIORITIZED", "FORMING"].map(s => (
          <button key={s} className={`chip ${stateFilter === s ? "active" : ""}`} onClick={() => setStateFilter(s)}>
            {s === "all" ? "All" : s.toLowerCase()} <span className="num">{counts[s]}</span>
          </button>
        ))}
        <span className="spacer" />
        <div className="search"><Icon name="search" size={12}/><input placeholder="search label, entity…" /></div>
        <button className="btn"><Icon name="filter" size={12}/>Filters</button>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: "38%" }}>Bucket</th>
              <th>State</th>
              <th>Score</th>
              <th className="num">Articles</th>
              <th>First seen</th>
              <th>Last update</th>
              <th>Velocity</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(b => (
              <tr key={b.id} className="row-clickable" onClick={() => { setSelectedBucket(b.id); setPage("bucket"); }}>
                <td>
                  <div style={{ fontFamily: "var(--font-serif)", fontSize: 14.5, fontWeight: 500 }}>{b.label}</div>
                  <div className="faint mono" style={{ fontSize: 10.5, marginTop: 2 }}>#{String(b.id).padStart(4, "0")} · {b.category}</div>
                </td>
                <td><StateBadge state={b.state} /></td>
                <td><ScoreCellWithTooltip p={b.p} m={b.m} g={b.g} total={b.score} vizMode={vizMode} /></td>
                <td className="num">{b.members}</td>
                <td className="mono faint" style={{ fontSize: 11.5 }}>{b.firstSeen}</td>
                <td className="mono faint" style={{ fontSize: 11.5 }}>{b.lastUpdate}</td>
                <td><Sparkbar data={b.sparkline} accent /></td>
                <td><Icon name="chevron" size={12}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

window.BucketsPage = BucketsPage;
