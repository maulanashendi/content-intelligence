// Bucket detail page

function BucketDetail({ bucketId, setPage, vizMode }) {
  const { BUCKETS, ANGLES } = window.CIData;
  const b = BUCKETS.find(x => x.id === bucketId) || BUCKETS[0];
  const bucketAngles = ANGLES.filter(a => a.bucketId === b.id);

  const persistPct = b.p ? (b.p / 33) * 100 : 0;
  const matPct = b.m ? (b.m / 33) * 100 : 0;
  const gapPct = b.g ? (b.g / 34) * 100 : 0;

  return (
    <div className="page-body" style={{ maxWidth: 1280 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, fontSize: 12, color: "var(--fg-faint)" }}>
        <button className="btn btn-ghost" onClick={() => setPage("dashboard")}>
          <Icon name="chevronLeft" size={12} /> Dashboard
        </button>
        <span>/</span>
        <span>Topic Bucket</span>
        <span>/</span>
        <span className="mono">#{String(b.id).padStart(4, "0")}</span>
      </div>

      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 22 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <StateBadge state={b.state} />
            <span className="mono faint" style={{ fontSize: 11 }}>{b.category} · first seen {b.firstSeen} · last update {b.lastUpdate}</span>
          </div>
          <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 32, fontWeight: 500, letterSpacing: "-0.02em", margin: 0, lineHeight: 1.15 }}>
            {b.label}
          </h1>
          <p style={{ marginTop: 8, color: "var(--fg-muted)", fontSize: 13.5, maxWidth: "62ch" }}>
            Auto-labeled cluster of {b.members} articles across {Math.ceil(b.members / 4)} sources. Centroid drift 0.08 (within tolerance). Reclustering not flagged.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn"><Icon name="bookmark" size={12} />Watch</button>
          <button className="btn"><Icon name="refresh" size={12} />Rescore</button>
          <button className="btn btn-primary"><Icon name="sparkle" size={12} />Generate angles</button>
        </div>
      </div>

      {/* Score hero */}
      <div className="score-hero" style={{ marginBottom: 22 }}>
        <div>
          <div className="score-hero-num">{b.score}<span className="of">/100</span></div>
          <div className="score-hero-state">{b.state.toLowerCase()}</div>
          <div className="faint mono" style={{ fontSize: 10.5, marginTop: 6 }}>computed 14:32 wib</div>
        </div>
        <div className="score-breakdown">
          <div className="row">
            <div className="label"><span className="swatch" style={{ background: "var(--persist)" }}/>Persistence</div>
            <div className="track"><div className="fill" style={{ width: `${persistPct}%`, background: "var(--persist)" }}/></div>
            <div className="v">{b.p}<span className="of">/33</span></div>
          </div>
          <div className="row">
            <div className="label"><span className="swatch" style={{ background: "var(--maturation)" }}/>Maturation</div>
            <div className="track"><div className="fill" style={{ width: `${matPct}%`, background: "var(--maturation)" }}/></div>
            <div className="v">{b.m}<span className="of">/33</span></div>
          </div>
          <div className="row">
            <div className="label"><span className="swatch" style={{ background: "var(--gap)" }}/>Information gap</div>
            <div className="track"><div className="fill" style={{ width: `${gapPct}%`, background: "var(--gap)" }}/></div>
            <div className="v">{b.g}<span className="of">/34</span></div>
          </div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 4, lineHeight: 1.5 }}>
            Coverage spans <strong>{Math.min(b.p ? Math.round(b.p / 33 * 14) : 0, 14)} distinct days</strong>.
            Pairwise embedding similarity <strong>{(1 - (b.m / 33) * 0.6).toFixed(2)}</strong> — articles diversifying.
            <strong> {b.entities ? b.entities.filter(e => e.gap).length : 3} entity gaps</strong> identified vs. published archive.
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="stack">
          {/* Generated angles */}
          <div className="card">
            <div className="card-head">
              <span className="card-title">Generated angles · bullet insights</span>
              <span className="card-meta">{bucketAngles.length} angles · generated 18m ago</span>
              <button className="btn btn-ghost"><Icon name="refresh" size={12}/>Regenerate</button>
            </div>
            <div style={{ padding: 14 }}>
              {bucketAngles.map((a, i) => (
                <div key={a.id} style={{ padding: i === 0 ? "0 0 16px" : "16px 0", borderTop: i ? "1px solid var(--line)" : "none" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                    <span className="angle-tag">AI suggestion</span>
                    <span className="badge badge-active">{a.format}</span>
                    <span className="faint mono" style={{ fontSize: 11 }}>{a.time}</span>
                    <span className="spacer" />
                    <span className="faint mono" style={{ fontSize: 11 }}>v{i + 1}</span>
                  </div>
                  <div className="angle-headline">{a.headline}</div>
                  <ul className="ci-bullets" style={{ marginTop: 8 }}>
                    <li><strong>Why it matters:</strong> {a.brief.split(".")[0]}.</li>
                    <li><strong>Reporting approach:</strong> {a.brief.split(".").slice(1, 2).join(".") || "field reporting + document tracing"}.</li>
                    <li><strong>Sources to pursue:</strong> {a.sources.slice(0, 3).join(", ")}{a.sources.length > 3 ? `, +${a.sources.length - 3} more` : ""}.</li>
                    <li><strong>Format:</strong> {a.format} · confidence {a.confidence}.</li>
                    <li className="ci-gap"><strong>Open lane:</strong> no competitor has covered this specific angle yet.</li>
                  </ul>
                </div>
              ))}
              {bucketAngles.length === 0 && (
                <div className="faint" style={{ padding: 20, textAlign: "center" }}>No angles generated yet for this bucket.</div>
              )}
            </div>
          </div>

          {/* Member articles */}
          <div className="card">
            <div className="card-head">
              <span className="card-title">Member articles</span>
              <span className="card-meta">{b.members} in cluster · most recent 5</span>
            </div>
            <div style={{ padding: "6px 16px 14px" }}>
              {(b.recentArticles || []).map((a, i) => (
                <div key={i} className="article-row">
                  <div className="article-title">{a.title}</div>
                  <div className="article-meta">
                    <span className="article-source">{a.source}</span>
                    <span>{a.time} ago</span>
                    <span>•</span>
                    <span>cluster sim 0.{84 + i}</span>
                    <span>•</span>
                    <Icon name="external" size={11}/>
                  </div>
                </div>
              ))}
              {(!b.recentArticles || !b.recentArticles.length) && (
                <div className="faint" style={{ padding: "10px 0" }}>
                  Cluster contains {b.members} articles. Listing collapsed for brevity.
                </div>
              )}
              <div style={{ marginTop: 10 }}>
                <button className="btn btn-ghost">View all {b.members} articles <Icon name="arrow" size={12}/></button>
              </div>
            </div>
          </div>
        </div>

        {/* Side */}
        <div className="stack">
          <div className="card">
            <div className="card-head">
              <span className="card-title">Top entities</span>
              <span className="card-meta">salience-weighted</span>
            </div>
            <div style={{ padding: 14, display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(b.entities || []).map(e => (
                <span key={e.t} className={`ent ${e.gap ? "gap" : ""}`} title={e.gap ? "Identified information gap" : ""}>
                  {e.t} <span className="freq">{e.n}</span>
                </span>
              ))}
            </div>
            <div style={{ padding: "0 14px 14px", fontSize: 11.5, color: "var(--fg-faint)" }}>
              <span className="ent gap" style={{ marginRight: 6 }}>green</span> = entity pair appears in cluster but not in published archive
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <span className="card-title">Velocity · 14d</span>
            </div>
            <div style={{ padding: 14 }}>
              <Sparkbar data={b.sparkline} accent />
              <div className="faint mono" style={{ fontSize: 11, marginTop: 8, lineHeight: 1.6 }}>
                day 1 → {b.sparkline[0]} arts<br/>
                day 7 → {b.sparkline[6] || 0} arts<br/>
                day 14 → {b.sparkline[b.sparkline.length - 1]} arts
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <span className="card-title">First reported</span>
              <span className="card-meta">early-mover timeline</span>
            </div>
            <div className="timeline">
              {(window.CIData.FIRST_REPORTED[b.id] || window.CIData.FIRST_REPORTED[1]).map((t, i) => (
                <div key={i} className={`tl-row ${t.first ? "first" : ""} ${t.tier === "self" ? "self" : ""} ${t.missing ? "missing" : ""}`}>
                  <div className="tl-dot" />
                  <div className="tl-content">
                    <div className="tl-head">
                      <span className="tl-source">{t.source}</span>
                      <span className="tl-tier">{t.outlet}</span>
                      {t.first && <span className="tl-first-tag">first</span>}
                      {t.tier === "self" && !t.missing && <span className="tl-self-tag">us</span>}
                      <span className="tl-time">{t.time}</span>
                    </div>
                    <div className="tl-title">{t.missing ? "no coverage yet — opportunity open" : t.title}</div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ padding: "10px 14px 14px", fontSize: 11.5, color: "var(--fg-faint)", borderTop: "1px solid var(--line)", marginTop: 4 }}>
              We are <strong style={{ color: "var(--bad)" }}>8 days behind</strong> the first wire. Lane still open at investigative tier.
            </div>
          </div>

          <div className="card">
            <div className="card-head"><span className="card-title">Audit trail</span></div>
            <div style={{ padding: 14, fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--fg-muted)", lineHeight: 1.7 }}>
              <div><span className="faint">14:32</span> rescore → {b.score}</div>
              <div><span className="faint">14:32</span> +1 article (Antara)</div>
              <div><span className="faint">13:18</span> angle batch v2 generated</div>
              <div><span className="faint">12:00</span> centroid drift 0.08</div>
              <div><span className="faint">08:32</span> state ACTIVE → RECOMMENDED</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.BucketDetail = BucketDetail;
