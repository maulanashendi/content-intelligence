// Angle queue page — competitor insights as bullet points

function AngleQueue() {
  const { ANGLES, BUCKETS } = window.CIData;

  // unique buckets only — one card per bucket
  const seen = new Set();
  const uniqueAngles = ANGLES.filter(a => {
    if (seen.has(a.bucketId)) return false;
    seen.add(a.bucketId);
    return true;
  });

  const competitorBullets = {
    1: [
      "Antara filed wire brief 8d ago — postur anggaran disepakati, no mention of Rp 2,1 T discrepancy.",
      "Detik ran 3 follow-ups but stayed on tunjangan profesi guru angle, missed the panja document trail.",
      "Kompas covered Mu'ti's denial; did not pursue who proposed the cut originally.",
      "Bisnis Indonesia framed it as fiscal story; missed the political dimension entirely.",
      "Republika and Liputan6 mostly republishing wire copy.",
      "No outlet has done document tracing across RKA-K/L versions 1–4.",
    ],
    2: [
      "Mongabay leading on environmental angle (11d ago first) — strong on hotspot data, weak on actor mapping.",
      "Antara wire briefs at 12-hour cadence; no investigative depth.",
      "CNN ID covered status siaga declaration; no follow-up on cause attribution.",
      "Tribun reposting BNPB statements verbatim.",
      "No outlet has cross-referenced 2019 SP3 case companies with current concession ownership.",
      "RSPO complaint board public records — untouched by anyone.",
    ],
    3: [
      "Tempo published the dapur pangkas porsi exposé 13d ago — strongest competitor coverage.",
      "Detik running daily breaking-news cadence on each new keracunan incident.",
      "Kompas economic desk filed budget angle, missed the supply chain angle.",
      "BGN's official Zoom anggaran response covered superficially across outlets.",
      "Sukoharjo / Klaten regional reporters undersupplied; supply chain reporting absent.",
      "No outlet has done end-to-end distribution trace from dapur to piring.",
    ],
    4: [
      "Tempo, Kompas, CNN ID covered the political statement; surface-level only.",
      "Detik framed as personality conflict, no structural analysis.",
      "RUU Parpol procedural reporting in Antara wire.",
      "No outlet has mapped which ketum benefits from current rule.",
      "Polling data on public opinion on jabatan pembatasan — uncollected.",
    ],
    5: [
      "Detik broke the new Kejagung announcement; mostly stenographic.",
      "Kompas ran a 1-paragraph wire copy.",
      "No outlet has reconstructed the 2025–2026 case timeline publicly.",
      "Tempo covered earlier 2024 chapter but did not update.",
      "Court documents from PN Tipikor — referenced by zero outlets in past 7d.",
    ],
  };

  return (
    <div className="page-body" style={{ maxWidth: 1100 }}>
      <div className="filterbar" style={{ marginBottom: 18 }}>
        <button className="chip active">All <span className="num">5</span></button>
        <button className="chip">High score <span className="num">3</span></button>
        <button className="chip">Politik <span className="num">3</span></button>
        <button className="chip">Lingkungan <span className="num">1</span></button>
        <button className="chip">Hukum <span className="num">1</span></button>
        <span className="spacer" />
        <div className="search">
          <Icon name="search" size={12} />
          <input placeholder="search bucket, outlet, entity…" />
        </div>
        <button className="btn"><Icon name="filter" size={12}/>Filters</button>
      </div>

      <div className="faint mono" style={{ fontSize: 11, padding: "0 0 10px" }}>
        what competitor outlets are publishing on each top bucket · captured insights only
      </div>

      {uniqueAngles.map(a => {
        const bucket = BUCKETS.find(b => b.id === a.bucketId);
        const bullets = competitorBullets[bucket.id] || [];
        return (
          <div key={a.id} className="ci-card">
            <div className="ci-card-head">
              <div>
                <div className="ci-card-label">#{String(bucket.id).padStart(4, "0")} · {bucket.category}</div>
                <div className="ci-card-title">{bucket.label}</div>
              </div>
              <div className="ci-card-meta">
                <span className="badge badge-recommended">score {bucket.score}</span>
                <span className="faint mono" style={{ fontSize: 11, marginTop: 4 }}>{bucket.members} articles · {bullets.length} insights</span>
              </div>
            </div>
            <ul className="ci-bullets ci-bullets-lg">
              {bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
            <div className="ci-card-foot">
              <span className="mono faint" style={{ fontSize: 10.5 }}>captured 14:32 wib · refreshed every cluster cycle</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

window.AngleQueue = AngleQueue;
