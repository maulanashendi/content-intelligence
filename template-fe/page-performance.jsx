// Performance attribution page

function Performance() {
  const { ASSIGNED_ANGLES } = window.CIData;
  const distribution = [
    { lab: "<6h", v: 4 },
    { lab: "6–12h", v: 9 },
    { lab: "12–24h", v: 14 },
    { lab: "1–2d", v: 18 },
    { lab: "2–4d", v: 11 },
    { lab: "4–7d", v: 6 },
    { lab: ">7d", v: 2 },
  ];
  const max = Math.max(...distribution.map(d => d.v));

  return (
    <div className="page-body" style={{ maxWidth: 1280 }}>
      <div className="grid grid-4" style={{ marginBottom: 22 }}>
        <div className="kpi">
          <div className="kpi-label">Angles generated · 7d</div>
          <div className="kpi-value">68<span className="delta delta-up">+12</span></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Acceptance rate</div>
          <div className="kpi-value">68%<span className="delta delta-up">+4pp</span></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Articles attributed</div>
          <div className="kpi-value">31<span className="delta delta-up">+5</span></div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>match rate 73%</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Gap address rate</div>
          <div className="kpi-value">52%<span className="delta delta-down">−3pp</span></div>
          <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>16 of 31 closed identified gaps</div>
        </div>
      </div>

      <div className="grid grid-feed">
        <div className="card">
          <div className="card-head">
            <span className="card-title">Time to publish · distribution</span>
            <span className="card-meta">accepted → published, last 7d</span>
          </div>
          <div style={{ padding: "12px 18px 18px" }}>
            <div className="barchart">
              {distribution.map(d => (
                <div key={d.lab} className="col">
                  <div className="val">{d.v}</div>
                  <div className="bar" style={{ height: `${(d.v / max) * 100}%` }} />
                  <div className="lab">{d.lab}</div>
                </div>
              ))}
            </div>
            <div className="faint" style={{ fontSize: 11.5, marginTop: 8, fontFamily: "var(--font-mono)" }}>
              median 22h · p90 4d 6h · longest 9d 2h
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <span className="card-title">Funnel · this week</span>
          </div>
          <div style={{ padding: 18 }}>
            {[
              { l: "Angles generated", v: 68, w: 100, c: "var(--fg)" },
              { l: "Pending review", v: 23, w: 34, c: "var(--info)" },
              { l: "Accepted", v: 46, w: 68, c: "var(--accent)" },
              { l: "Dismissed", v: 22, w: 32, c: "var(--fg-faint)" },
              { l: "Published", v: 31, w: 46, c: "var(--ok)" },
              { l: "Gap addressed", v: 16, w: 24, c: "var(--gap)" },
            ].map(f => (
              <div key={f.l} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                  <span>{f.l}</span>
                  <span className="mono" style={{ color: "var(--fg)", fontVariantNumeric: "tabular-nums" }}>{f.v}</span>
                </div>
                <div style={{ height: 6, background: "var(--bg-sunken)", borderRadius: 2, border: "1px solid var(--line)", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${f.w}%`, background: f.c, opacity: 0.85 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="sect-head">
        <h3>Top performing angles</h3>
        <span className="count">by match confidence × gap addressed</span>
      </div>
      <div className="card">
        {ASSIGNED_ANGLES.map((a, i) => (
          <div key={a.id} className="top-angle">
            <span className="rank">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <div className="head">{a.headline}</div>
              <div className="faint mono" style={{ fontSize: 11, marginTop: 3 }}>
                {a.assignee} · assigned {a.assigned} ago · {a.gap ? "gap addressed" : "no gap match"}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="conf">{(a.confidence * 100).toFixed(0)}% match</div>
              {a.gap && <div className="badge badge-ok" style={{ marginTop: 3 }}><Icon name="target" size={10}/>gap closed</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

window.Performance = Performance;
