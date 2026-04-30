// Desk Insight page — drill into one editorial desk (politik, lingkungan, hukum, etc.)
// Shows everything scoped to that category: top buckets, keywords, angles, articles, feeds.

function DeskInsight({ desk, setSelectedBucket, setPage }) {
  const { BUCKETS, KEYWORDS, ANGLES, FEEDS } = window.CIData;
  const [tab, setTab] = React.useState("overview");

  // Filter to this desk
  const deskBuckets = BUCKETS.filter(b => b.category === desk);
  const deskFeeds = FEEDS.filter(f => f.category === desk);
  const deskBucketIds = new Set(deskBuckets.map(b => b.id));
  const deskAngles = ANGLES.filter(a => deskBucketIds.has(a.bucketId));
  const deskKeywords = KEYWORDS.filter(k => k.buckets && k.buckets.some(id => deskBucketIds.has(id)));

  // Aggregate stats
  const totalArticles = deskBuckets.reduce((s, b) => s + (b.members || 0), 0);
  const recommendedCount = deskBuckets.filter(b => b.state === "RECOMMENDED").length;
  const matureCount = deskBuckets.filter(b => b.state === "MATURE").length;
  const activeCount = deskBuckets.filter(b => b.state === "ACTIVE").length;
  const watchingCount = deskBuckets.filter(b => b.state === "WATCHING").length;

  const sortedBuckets = [...deskBuckets].sort((a, b) => (b.score || 0) - (a.score || 0));
  const topBucket = sortedBuckets[0];

  // Desk meta — short editorial frame for each desk
  const deskMeta = {
    politik: {
      lead: "Politik desk",
      blurb: "DPR, parpol, kabinet, anggaran, kebijakan publik. Tracking 4 active feeds, 4 buckets in rolling window.",
      accent: "oklch(0.55 0.18 25)",
      lead_editor: "Maulana Shendi",
      bullets: [
        "Anggaran Pendidikan dominates desk volume on day 8 — investigative lane still open.",
        "Pembatasan Jabatan Ketum is the freshest entry; only 3 outlets covering at surface tier.",
        "MBG bucket leaks across politik / hukum boundary — coordinate with Hukum desk.",
      ],
    },
    lingkungan: {
      lead: "Lingkungan desk",
      blurb: "Karhutla, banjir, deforestasi, polusi, perubahan iklim. 2 active feeds — one failing.",
      accent: "oklch(0.5 0.15 145)",
      lead_editor: "Bayu R.",
      bullets: [
        "Karhutla Riau approaching peak Trends interest. Only Mongabay leading on environment angle.",
        "Banjir Rob Pesisir Utara entering ACTIVE state — early signal worth assigning.",
        "Kompas Lingkungan feed FAILING for 1h 14m — ask infra to investigate.",
      ],
    },
    hukum: {
      lead: "Hukum desk",
      blurb: "Kejagung, KPK, Polri, peradilan, kasus korupsi, kekerasan anak. 1 feed.",
      accent: "oklch(0.45 0.15 285)",
      lead_editor: "Astrid W.",
      bullets: [
        "Hery Susanto / Kejagung — Trends jumped +24 after surprise statement; coverage still wire-only.",
        "Daycare Yogyakarta in MATURE state with assigned story (Astrid).",
        "Tirto Riset feed dead 9h 22m — losing investigative law signal.",
      ],
    },
    ekonomi: {
      lead: "Ekonomi desk",
      blurb: "Anggaran negara, perdagangan, ekspor-impor, fiskal, perbankan, korporasi. 2 feeds.",
      accent: "oklch(0.55 0.14 65)",
      lead_editor: "Rini S.",
      bullets: [
        "JP Morgan / Ketahanan Energi maturing — analytical angle still open.",
        "Tarif AS / Tekstil dropped 12 positions — fading signal, deprioritize.",
        "Cukai Rokok 2027 in WATCHING; revisit when DPR komisi XI agenda updates.",
      ],
    },
    umum: {
      lead: "Umum desk",
      blurb: "Berita umum, peristiwa, sosial, hari besar. Cross-desk catch-all.",
      accent: "oklch(0.5 0.05 250)",
      lead_editor: "Editor on duty",
      bullets: [
        "Hari Tari Sedunia / Semarang — feature angle for weekend edition.",
        "Use this desk only as fallback; route to specific desks where possible.",
      ],
    },
    investigasi: {
      lead: "Investigasi desk",
      blurb: "Cross-desk deep reporting. Pulls from Tribun Investigasi and Tirto Riset.",
      accent: "oklch(0.4 0.16 25)",
      lead_editor: "Maulana Shendi",
      bullets: [
        "Tirto Riset feed DEAD — primary investigative source offline.",
        "Tribun Investigasi healthy, 38 articles in window.",
        "Cross-reference with politik (anggaran) and lingkungan (karhutla) desks.",
      ],
    },
    tokoh: {
      lead: "Tokoh desk",
      blurb: "Profile, sastra, film, seni, budaya. Personality-driven coverage.",
      accent: "oklch(0.5 0.13 320)",
      lead_editor: "A. Nasery",
      bullets: [
        "Wregas Bhanuteja / Bakmi / Film — light personality piece live now.",
        "Chairil Anwar 77 Tahun — column assigned (A. Nasery).",
        "Festival Film Lokarno bucket FORMING — watch for Indonesian selection news.",
      ],
    },
  };

  const meta = deskMeta[desk] || {
    lead: `${desk} desk`,
    blurb: "—",
    accent: "var(--accent-fg)",
    lead_editor: "—",
    bullets: [],
  };

  return (
    <div className="page-body" style={{ maxWidth: 1280 }}>
      {/* Back link */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <button className="btn btn-ghost" onClick={() => setPage("dashboard")}>
          <Icon name="chevronLeft" size={12} />Dashboard
        </button>
        <span className="faint mono" style={{ fontSize: 11 }}>·</span>
        <span className="faint mono" style={{ fontSize: 11 }}>desk insight</span>
      </div>

      {/* Hero */}
      <div className="desk-hero" style={{ borderColor: meta.accent }}>
        <div className="desk-hero-rail" style={{ background: meta.accent }} />
        <div className="desk-hero-body">
          <div className="desk-hero-tag mono">desk · {desk}</div>
          <h1 className="desk-hero-title">
            <span className="serif italic" style={{ color: meta.accent }}>{meta.lead}</span> <span className="faint">— editorial intelligence</span>
          </h1>
          <p className="desk-hero-blurb">{meta.blurb}</p>
          <div className="desk-hero-meta">
            <div><span className="faint mono">lead editor</span> <strong>{meta.lead_editor}</strong></div>
            <div><span className="faint mono">feeds</span> <strong>{deskFeeds.length}</strong></div>
            <div><span className="faint mono">buckets</span> <strong>{deskBuckets.length}</strong></div>
            <div><span className="faint mono">articles · 14d</span> <strong>{totalArticles}</strong></div>
            <div><span className="faint mono">angles pending</span> <strong>{deskAngles.length}</strong></div>
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-4" style={{ margin: "18px 0" }}>
        <div className="kpi">
          <div className="kpi-label">Recommended</div>
          <div className="kpi-value" style={{ color: meta.accent }}>{recommendedCount}</div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>top-priority buckets</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Mature + Active</div>
          <div className="kpi-value">{matureCount + activeCount}</div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>{matureCount} mature · {activeCount} active</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Watching</div>
          <div className="kpi-value">{watchingCount}</div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>early signal</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Top score</div>
          <div className="kpi-value">{topBucket?.score ?? "—"}</div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>{topBucket ? topBucket.label.split(" / ")[0] : "—"}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="filterbar" style={{ marginBottom: 16 }}>
        <button className={`chip ${tab === "overview" ? "active" : ""}`} onClick={() => setTab("overview")}>Overview</button>
        <button className={`chip ${tab === "buckets" ? "active" : ""}`} onClick={() => setTab("buckets")}>Buckets <span className="num">{deskBuckets.length}</span></button>
        <button className={`chip ${tab === "keywords" ? "active" : ""}`} onClick={() => setTab("keywords")}>Keywords <span className="num">{deskKeywords.length}</span></button>
        <button className={`chip ${tab === "angles" ? "active" : ""}`} onClick={() => setTab("angles")}>Angles <span className="num">{deskAngles.length}</span></button>
        <button className={`chip ${tab === "articles" ? "active" : ""}`} onClick={() => setTab("articles")}>Articles</button>
        <button className={`chip ${tab === "feeds" ? "active" : ""}`} onClick={() => setTab("feeds")}>Feeds <span className="num">{deskFeeds.length}</span></button>
      </div>

      {tab === "overview" && (
        <DeskOverview
          desk={desk} meta={meta} buckets={sortedBuckets} keywords={deskKeywords}
          angles={deskAngles} feeds={deskFeeds}
          setSelectedBucket={setSelectedBucket} setPage={setPage}
        />
      )}
      {tab === "buckets" && (
        <DeskBuckets buckets={sortedBuckets} setSelectedBucket={setSelectedBucket} setPage={setPage} />
      )}
      {tab === "keywords" && <DeskKeywords keywords={deskKeywords} />}
      {tab === "angles" && <DeskAngles angles={deskAngles} buckets={deskBuckets} />}
      {tab === "articles" && <DeskArticles buckets={deskBuckets} />}
      {tab === "feeds" && <DeskFeeds feeds={deskFeeds} />}
    </div>
  );
}

// ---------- OVERVIEW ----------
function DeskOverview({ desk, meta, buckets, keywords, angles, feeds, setSelectedBucket, setPage }) {
  const top = buckets.slice(0, 5);
  const topKw = keywords.slice(0, 6);
  const recArticles = buckets.flatMap(b => (b.recentArticles || []).map(a => ({ ...a, bucket: b }))).slice(0, 6);

  return (
    <div className="grid grid-main">
      <div className="stack">
        {/* AI desk briefing */}
        <div className="card briefing">
          <div className="card-head">
            <span className="card-title"><span className="ai-dot" />Desk briefing · {desk}</span>
            <span className="card-meta">generated 14:32 wib · refreshes every 6h</span>
          </div>
          <div className="briefing-body">
            <p className="briefing-greeting">
              <span className="serif italic">State of the {desk} desk.</span> Here's what's moving across {feeds.length} feeds and {buckets.length} active buckets in this desk's window.
            </p>
            <div className="briefing-section">
              <div className="briefing-h">DESK SIGNAL</div>
              <ul className="briefing-list">
                {meta.bullets.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            </div>
            <div className="briefing-foot">
              <span className="mono faint" style={{ fontSize: 10.5 }}>summary scoped to desk · {buckets.length} buckets · {keywords.length} keywords · {angles.length} angles</span>
            </div>
          </div>
        </div>

        {/* Top buckets */}
        <div className="card">
          <div className="card-head">
            <span className="card-title">Top buckets · {desk}</span>
            <span className="card-meta">sorted by deep info score</span>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: "44%" }}>Bucket</th>
                <th>State</th>
                <th>Score</th>
                <th className="num">Articles</th>
                <th>Trend · 14d</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {top.map(b => (
                <tr key={b.id} className="row-clickable" onClick={() => { setSelectedBucket(b.id); setPage("bucket"); }}>
                  <td>
                    <div style={{ fontFamily: "var(--font-serif)", fontSize: 14.5, fontWeight: 500 }}>{b.label}</div>
                    <div className="faint mono" style={{ fontSize: 10.5, marginTop: 2 }}>#{String(b.id).padStart(4, "0")}</div>
                  </td>
                  <td><StateBadge state={b.state} /></td>
                  <td><ScoreCellWithTooltip p={b.p} m={b.m} g={b.g} total={b.score} /></td>
                  <td className="num">{b.members}</td>
                  <td><Sparkbar data={b.sparkline} accent /></td>
                  <td><Icon name="chevron" size={12}/></td>
                </tr>
              ))}
              {top.length === 0 && (
                <tr><td colSpan="6" className="faint" style={{ padding: 24, textAlign: "center" }}>No buckets in this desk yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Recent articles */}
        <div className="card">
          <div className="card-head">
            <span className="card-title">Recent articles · {desk}</span>
            <span className="card-meta">across all desk buckets</span>
          </div>
          <div>
            {recArticles.map((a, i) => (
              <div key={i} className="article-row">
                <div className="article-time mono">{a.time}</div>
                <div>
                  <div className="article-title">{a.title}</div>
                  <div className="faint mono" style={{ fontSize: 10.5, marginTop: 2 }}>
                    {a.source} · <span style={{ color: "var(--fg-muted)" }}>{a.bucket.label.split(" / ")[0]}</span>
                  </div>
                </div>
              </div>
            ))}
            {recArticles.length === 0 && (
              <div className="faint" style={{ padding: 24, textAlign: "center" }}>No recent articles.</div>
            )}
          </div>
        </div>
      </div>

      {/* Right column */}
      <div className="stack">
        {/* Desk keywords */}
        <div className="card">
          <div className="card-head">
            <span className="card-title">Rising keywords</span>
            <span className="card-meta">scoped to {desk}</span>
          </div>
          <div>
            {topKw.map((k, i) => (
              <div key={k.kw} className="kw-row">
                <span className="kw-rank">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <div className="kw-name">{k.kw}</div>
                  <div className="kw-trend">rss {k.rss} · trend {k.trend ?? "—"} · gsc {k.gsc ?? "—"}</div>
                </div>
                {k.flag === "rising" && <span className="badge badge-rising"><Icon name="arrowUp" size={10}/>rising</span>}
                {k.flag === "new" && <span className="badge badge-new">new</span>}
                {k.flag === "fading" && <span className="badge badge-fading"><Icon name="arrowDown" size={10}/>fading</span>}
                {!k.flag && <span></span>}
                <span className="mono" style={{ fontSize: 12, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{k.comp}</span>
              </div>
            ))}
            {topKw.length === 0 && (
              <div className="faint" style={{ padding: 24, textAlign: "center" }}>No keywords scoped here yet.</div>
            )}
          </div>
        </div>

        {/* Feed health */}
        <div className="card">
          <div className="card-head">
            <span className="card-title">Feeds · {desk}</span>
            <span className="card-meta">{feeds.length} sources</span>
          </div>
          <div>
            {feeds.map(f => (
              <div key={f.id} className="feed-row" style={{ gridTemplateColumns: "10px 1.4fr auto" }}>
                <span className={`dot-status ${f.status === "OK" ? "dot-ok" : f.status === "FAILING" ? "dot-warn" : "dot-bad"}`}></span>
                <div>
                  <div className="feed-name">{f.name}</div>
                  <div className="feed-meta">{f.lastFetch} · {f.count} arts</div>
                </div>
                <StateBadge state={f.status} />
              </div>
            ))}
            {feeds.length === 0 && (
              <div className="faint" style={{ padding: 24, textAlign: "center" }}>No feeds in this desk.</div>
            )}
          </div>
        </div>

        {/* Angles preview */}
        <div className="card">
          <div className="card-head">
            <span className="card-title">Open angles</span>
            <span className="card-meta">{angles.length} suggested</span>
          </div>
          <div className="ci-list">
            {angles.slice(0, 3).map(a => (
              <div key={a.id} className="ci-block">
                <div className="ci-block-head">
                  <span className="serif" style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.35 }}>{a.headline}</span>
                </div>
                <div className="faint mono" style={{ fontSize: 10.5, marginTop: 4 }}>{a.format} · {a.confidence} confidence · {a.time}</div>
              </div>
            ))}
            {angles.length === 0 && (
              <div className="faint" style={{ padding: 24, textAlign: "center" }}>No angles yet.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- BUCKETS TAB ----------
function DeskBuckets({ buckets, setSelectedBucket, setPage }) {
  return (
    <div className="card">
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
          {buckets.map(b => (
            <tr key={b.id} className="row-clickable" onClick={() => { setSelectedBucket(b.id); setPage("bucket"); }}>
              <td>
                <div style={{ fontFamily: "var(--font-serif)", fontSize: 14.5, fontWeight: 500 }}>{b.label}</div>
                <div className="faint mono" style={{ fontSize: 10.5, marginTop: 2 }}>#{String(b.id).padStart(4, "0")}</div>
              </td>
              <td><StateBadge state={b.state} /></td>
              <td><ScoreCellWithTooltip p={b.p} m={b.m} g={b.g} total={b.score} /></td>
              <td className="num">{b.members}</td>
              <td className="mono faint" style={{ fontSize: 11.5 }}>{b.firstSeen}</td>
              <td className="mono faint" style={{ fontSize: 11.5 }}>{b.lastUpdate}</td>
              <td><Sparkbar data={b.sparkline} accent /></td>
              <td><Icon name="chevron" size={12}/></td>
            </tr>
          ))}
          {buckets.length === 0 && (
            <tr><td colSpan="8" className="faint" style={{ padding: 24, textAlign: "center" }}>No buckets in this desk.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---------- KEYWORDS TAB ----------
function DeskKeywords({ keywords }) {
  return (
    <div className="card">
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: "30%" }}>Keyword</th>
            <th className="num">RSS</th>
            <th className="num">Trends</th>
            <th className="num">GSC</th>
            <th className="num">Composite</th>
            <th>Flag</th>
          </tr>
        </thead>
        <tbody>
          {keywords.map(k => (
            <tr key={k.kw}>
              <td><div style={{ fontFamily: "var(--font-serif)", fontSize: 14, fontWeight: 500 }}>{k.kw}</div></td>
              <td className="num">{k.rss}</td>
              <td className="num">{k.trend ?? "—"}</td>
              <td className="num">{k.gsc ?? "—"}</td>
              <td className="num"><strong>{k.comp}</strong></td>
              <td>
                {k.flag === "rising" && <span className="badge badge-rising"><Icon name="arrowUp" size={10}/>rising</span>}
                {k.flag === "new" && <span className="badge badge-new">new</span>}
                {k.flag === "fading" && <span className="badge badge-fading"><Icon name="arrowDown" size={10}/>fading</span>}
                {!k.flag && <span className="faint mono" style={{ fontSize: 11 }}>—</span>}
              </td>
            </tr>
          ))}
          {keywords.length === 0 && (
            <tr><td colSpan="6" className="faint" style={{ padding: 24, textAlign: "center" }}>No keywords scoped here.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---------- ANGLES TAB ----------
function DeskAngles({ angles, buckets }) {
  return (
    <div>
      {angles.map(a => {
        const bucket = buckets.find(b => b.id === a.bucketId);
        return (
          <div key={a.id} className="ci-card">
            <div className="ci-card-head">
              <div>
                <div className="ci-card-label">{bucket ? `#${String(bucket.id).padStart(4, "0")} · ${bucket.label}` : ""}</div>
                <div className="ci-card-title">{a.headline}</div>
              </div>
              <div className="ci-card-meta">
                <span className="badge badge-active">{a.format}</span>
                <span className="faint mono" style={{ fontSize: 11, marginTop: 4 }}>{a.confidence} confidence</span>
              </div>
            </div>
            <div className="angle-brief" style={{ marginBottom: 10 }}>{a.brief}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              <span className="faint mono" style={{ fontSize: 11, marginRight: 4 }}>sources to pursue:</span>
              {a.sources.map(s => <span key={s} className="ent">{s}</span>)}
            </div>
            <div className="ci-card-foot">
              <span className="mono faint" style={{ fontSize: 10.5 }}>generated {a.time}</span>
            </div>
          </div>
        );
      })}
      {angles.length === 0 && (
        <div className="card" style={{ padding: 32, textAlign: "center" }}>
          <div className="faint">No angles generated for this desk yet.</div>
        </div>
      )}
    </div>
  );
}

// ---------- ARTICLES TAB ----------
function DeskArticles({ buckets }) {
  const all = buckets.flatMap(b => (b.recentArticles || []).map(a => ({ ...a, bucket: b })));
  return (
    <div className="card">
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: 110 }}>Time</th>
            <th>Title</th>
            <th>Source</th>
            <th>Bucket</th>
          </tr>
        </thead>
        <tbody>
          {all.map((a, i) => (
            <tr key={i}>
              <td className="mono faint" style={{ fontSize: 11.5 }}>{a.time}</td>
              <td><div style={{ fontFamily: "var(--font-serif)", fontSize: 13.5, lineHeight: 1.4 }}>{a.title}</div></td>
              <td className="mono" style={{ fontSize: 11.5 }}>{a.source}</td>
              <td className="faint" style={{ fontSize: 12 }}>{a.bucket.label.split(" / ")[0]}</td>
            </tr>
          ))}
          {all.length === 0 && (
            <tr><td colSpan="4" className="faint" style={{ padding: 24, textAlign: "center" }}>No articles indexed yet for this desk.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---------- FEEDS TAB ----------
function DeskFeeds({ feeds }) {
  return (
    <div className="card">
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: 30 }}></th>
            <th>Feed</th>
            <th>Category</th>
            <th className="num">Articles</th>
            <th>Last fetch</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {feeds.map(f => (
            <tr key={f.id}>
              <td><span className={`dot-status ${f.status === "OK" ? "dot-ok" : f.status === "FAILING" ? "dot-warn" : "dot-bad"}`}></span></td>
              <td><div style={{ fontFamily: "var(--font-serif)", fontSize: 14, fontWeight: 500 }}>{f.name}</div></td>
              <td className="mono faint" style={{ fontSize: 11.5 }}>{f.category}</td>
              <td className="num">{f.count}</td>
              <td className="mono faint" style={{ fontSize: 11.5 }}>{f.lastFetch}</td>
              <td><StateBadge state={f.status} /></td>
            </tr>
          ))}
          {feeds.length === 0 && (
            <tr><td colSpan="6" className="faint" style={{ padding: 24, textAlign: "center" }}>No feeds in this desk.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

window.DeskInsight = DeskInsight;
