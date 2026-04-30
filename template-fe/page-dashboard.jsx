// Dashboard page

function Dashboard({ vizMode, setPage, setSelectedBucket }) {
  const { FEEDS, BUCKETS, KEYWORDS, ANGLES } = window.CIData;
  const sorted = [...BUCKETS].sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 8);
  const recommendedCount = BUCKETS.filter((b) => b.state === "RECOMMENDED").length;

  return (
    <div className="page-body">
      {/* KPIs */}
      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        <div className="kpi">
          <div className="kpi-label">Recommended buckets</div>
          <div className="kpi-value">{recommendedCount}<span className="delta delta-up">+3</span></div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>vs. yesterday</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Pending angles</div>
          <div className="kpi-value">23<span className="delta delta-up">+5</span></div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>across 14 buckets</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Articles · last 24h</div>
          <div className="kpi-value">412<span className="delta delta-down">−18</span></div>
          <Sparkbar data={[12, 18, 22, 19, 28, 32, 29, 38, 41, 36, 44, 52, 48, 46, 52, 49, 44, 38, 42, 46, 52, 48, 42, 38]} accent />
        </div>
        <div className="kpi">
          <div className="kpi-label">Acceptance rate · 7d</div>
          <div className="kpi-value">68%<span className="delta delta-up">+4pp</span></div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>27 of 40 angles accepted</div>
        </div>
      </div>

      <div className="grid grid-main">
        {/* Left column */}
        <div className="stack">
          {/* AI assistant briefing */}
          <div className="card briefing">
            <div className="card-head">
              <span className="card-title"><span className="ai-dot" />AI editorial briefing</span>
              <span className="card-meta">generated 14:32 wib · refreshes every 6h</span>
              <button className="btn btn-ghost"><Icon name="refresh" size={12} />Regenerate</button>
            </div>
            <div className="briefing-body" style={{ fontFamily: "\"Source Serif 4\"" }}>
              <p className="briefing-greeting" style={{ color: "rgb(37, 24, 24)" }}>
                <span className="serif italic">Selamat siang, Maulana.</span> Here's where the news cycle stands across our 4,812 article window — and where we have an opening.
              </p>

              <div className="briefing-section">
                <div className="briefing-h" style={{ fontFamily: "\"Source Serif 4\"" }}>HOTTEST RIGHT NOW</div>
                <ul className="briefing-list">
                  <li style={{ fontFamily: "\"Source Serif 4\"" }}><strong>Makan Bergizi Gratis</strong> dominates trends (composite 94, +12 in 6h). 62 articles across 9 outlets — story is mature but still escalating.</li>
                  <li style={{ fontFamily: "\"Source Serif 4\"" }}><strong>Karhutla Riau</strong> is approaching peak Google interest (95). Hotspot count in Pelalawan jumped to 142 overnight.</li>
                  <li style={{ fontFamily: "\"Source Serif 4\"" }}><strong>Anggaran Pendidikan</strong> sustaining steady volume on day 8 — persistence score now 31/33.</li>
                </ul>
              </div>

              <div className="briefing-section">
                <div className="briefing-h" style={{ fontFamily: "\"Source Serif 4\"" }}>RISING IN THE LAST 24H</div>
                <ul className="briefing-list" style={{ fontFamily: "\"Source Serif 4\"" }}>
                  <li><strong>Pembatasan Jabatan Ketum</strong> — new entry, 6 articles in 24h, 0 analysis pieces yet.</li>
                  <li><strong>Hery Susanto / Kejagung</strong> — Trends jumped +24 after surprise statement; coverage still wire-only.</li>
                  <li><strong>Konsesi Sawit</strong> entered keyword top 20 for the first time this quarter.</li>
                </ul>
              </div>

              <div className="briefing-section" style={{ fontFamily: "\"Source Serif 4\"" }}>
                <div className="briefing-h">WHERE WE HAVE A LANE</div>
                <ul className="briefing-list">
                  <li><strong>Anggaran Pendidikan</strong> — only Antara and Detik covering, both surface-level. <em>Investigative lane open 3 days.</em></li>
                  <li><strong>Karhutla Riau</strong> — Mongabay leading on environment angle. <em>Nobody has connected the 2019 SP3 thread.</em></li>
                  <li><strong>Pembatasan Jabatan Ketum</strong> — 3 outlets at surface tier. <em>No power-mapping analysis published anywhere.</em></li>
                </ul>
              </div>

              <div className="briefing-section">
                <div className="briefing-h">WHAT WE SHOULD BE WATCHING</div>
                <ul className="briefing-list">
                  <li><strong>Tarif AS / Tekstil</strong> dropped 12 positions — fading; deprioritize.</li>
                  <li><strong>Tirto Riset feed</strong> dead 9h 22m — losing investigative source signal.</li>
                  <li>Bucket #0001 centroid drift at 0.08 — within tolerance but trending up; review if it crosses 0.15.</li>
                </ul>
              </div>

              <div className="briefing-foot">
                <span className="mono faint" style={{ fontSize: 10.5 }}>summary based on 142 active buckets · 20 keyword signals · 12 feeds</span>
              </div>
            </div>
          </div>

          {/* Top buckets */}
          <div className="card">
            <div className="card-head">
              <span className="card-title">Top topic buckets</span>
              <span className="card-meta">sorted by deep info score</span>
              <button className="btn btn-ghost" onClick={() => setPage("buckets")}>
                view all <Icon name="arrow" size={12} />
              </button>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: "44%" }}>Bucket</th>
                  <th style={{ width: 110 }}>State</th>
                  <th>Score</th>
                  <th className="num">Articles</th>
                  <th>Trend · 14d</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((b) =>
                <tr key={b.id} className="row-clickable" onClick={() => {setSelectedBucket(b.id);setPage("bucket");}}>
                    <td>
                      <div style={{ fontFamily: "var(--font-serif)", fontSize: 14.5, fontWeight: 500, lineHeight: 1.3 }}>{b.label}</div>
                      <div className="faint mono" style={{ fontSize: 10.5, marginTop: 2 }}>#{String(b.id).padStart(4, "0")} · {b.category}</div>
                    </td>
                    <td><StateBadge state={b.state} /></td>
                    <td><ScoreCellWithTooltip p={b.p} m={b.m} g={b.g} total={b.score} vizMode={vizMode} /></td>
                    <td className="num">{b.members}</td>
                    <td><Sparkbar data={b.sparkline} accent /></td>
                    <td><Icon name="chevron" size={12} /></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Competitor insights — bullet form */}
          <div className="card">
            <div className="card-head">
              <span className="card-title">Competitor coverage · bullet insights</span>
              <span className="card-meta">what other outlets just published</span>
              <button className="btn btn-ghost" onClick={() => setPage("queue")}>open all <Icon name="arrow" size={12} /></button>
            </div>
            <div className="ci-list">
              {ANGLES.slice(0, 3).map((a) => {
                const bucket = BUCKETS.find((b) => b.id === a.bucketId);
                return (
                  <div key={a.id} className="ci-block">
                    <div className="ci-block-head">
                      <span className="serif" style={{ fontSize: 14, fontWeight: 500 }}>{bucket.label.split(" / ")[0]}</span>
                      <span className="faint mono" style={{ fontSize: 11 }}>#{String(bucket.id).padStart(4, "0")} · score {bucket.score}</span>
                    </div>
                    <ul className="ci-bullets">
                      <li><strong>Antara</strong> covered the wire angle 8d ago — surface only, no follow-up.</li>
                      <li><strong>Kompas</strong> framed it as policy debate; missed the {a.bucketId === 1 ? "Rp 2,1 T discrepancy" : a.bucketId === 2 ? "2019 SP3 connection" : "rantai dingin distribusi"}.</li>
                      <li><strong>Detik</strong> running breaking-news cadence (3 posts/day), no analysis layer.</li>
                      <li className="ci-gap"><strong>Open angle:</strong> {a.headline.toLowerCase()}</li>
                    </ul>
                  </div>);

              })}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="stack">
          {/* Feed health */}
          <div className="card">
            <div className="card-head">
              <span className="card-title">Feed health</span>
              <span className="card-meta">12 sources</span>
            </div>
            <div>
              {FEEDS.slice(0, 8).map((f) =>
              <div key={f.id} className="feed-row" style={{ gridTemplateColumns: "10px 1.4fr auto" }}>
                  <span className={`dot-status ${f.status === "OK" ? "dot-ok" : f.status === "FAILING" ? "dot-warn" : "dot-bad"}`}></span>
                  <div>
                    <div className="feed-name">{f.name}</div>
                    <div className="feed-meta">{f.lastFetch} · {f.count} arts</div>
                  </div>
                  <StateBadge state={f.status} />
                </div>
              )}
            </div>
          </div>

          {/* Hot keywords */}
          <div className="card">
            <div className="card-head">
              <span className="card-title">Rising keywords</span>
              <button className="btn btn-ghost" onClick={() => setPage("keywords")}>all <Icon name="arrow" size={12} /></button>
            </div>
            <div>
              {KEYWORDS.slice(0, 8).map((k, i) =>
              <div key={k.kw} className="kw-row">
                  <span className="kw-rank">{String(i + 1).padStart(2, "0")}</span>
                  <div>
                    <div className="kw-name">{k.kw}</div>
                    <div className="kw-trend">rss {k.rss} · trend {k.trend ?? "—"} · gsc {k.gsc ?? "—"}</div>
                  </div>
                  {k.flag === "rising" && <span className="badge badge-rising"><Icon name="arrowUp" size={10} />rising</span>}
                  {k.flag === "new" && <span className="badge badge-new">new</span>}
                  {k.flag === "fading" && <span className="badge badge-fading"><Icon name="arrowDown" size={10} />fading</span>}
                  {!k.flag && <span></span>}
                  <span className="mono" style={{ fontSize: 12, color: "var(--fg)", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{k.comp}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>);

}

window.Dashboard = Dashboard;