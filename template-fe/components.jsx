// Reusable components
const { useState, useRef, useEffect } = React;

function Icon({ name, size = 14 }) {
  const paths = {
    home: <path d="M3 11l9-8 9 8M5 9v12h14V9" />,
    inbox: <><path d="M3 13h5l1 3h6l1-3h5" /><path d="M5 4h14l2 9v7H3v-7z" /></>,
    chart: <><path d="M3 21h18" /><path d="M6 17V9M11 17V5M16 17v-7M21 17v-4" /></>,
    layers: <><path d="M12 3l9 5-9 5-9-5 9-5z" /><path d="M3 13l9 5 9-5M3 17l9 5 9-5" /></>,
    activity: <path d="M3 12h4l3-9 4 18 3-9h4" />,
    radio: <><circle cx="12" cy="12" r="2" /><path d="M16.2 7.8a6 6 0 0 1 0 8.4M7.8 16.2a6 6 0 0 1 0-8.4M19 5a10 10 0 0 1 0 14M5 19A10 10 0 0 1 5 5" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
    chevron: <path d="M9 6l6 6-6 6" />,
    chevronDown: <path d="M6 9l6 6 6-6" />,
    chevronLeft: <path d="M15 6l-6 6 6 6" />,
    check: <path d="M5 12l5 5L20 7" />,
    x: <path d="M6 6l12 12M18 6l-12 12" />,
    edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z" /></>,
    sparkle: <><path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z" /><path d="M19 14l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" /></>,
    refresh: <><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></>,
    filter: <path d="M4 5h16M7 12h10M10 19h4" />,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></>,
    bookmark: <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />,
    rss: <><path d="M4 11a9 9 0 0 1 9 9" /><path d="M4 4a16 16 0 0 1 16 16" /><circle cx="5" cy="19" r="1.5" fill="currentColor" stroke="none" /></>,
    target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    trending: <><path d="M3 17l6-6 4 4 8-8" /><path d="M14 7h7v7" /></>,
    arrowUp: <path d="M12 19V5M5 12l7-7 7 7" />,
    arrowDown: <path d="M12 5v14M5 12l7 7 7-7" />,
    external: <><path d="M14 4h6v6" /><path d="M10 14L20 4" /><path d="M19 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h6" /></>,
    book: <><path d="M4 19V5a2 2 0 0 1 2-2h14v18H6a2 2 0 0 1-2-2z" /><path d="M4 19a2 2 0 0 1 2-2h14" /></>,
    flag: <><path d="M4 22V4M4 4h13l-2 4 2 4H4" /></>
  };
  return (
    <svg className={`icon ${size === 12 ? 'sm' : ''}`} viewBox="0 0 24 24" style={{ width: size, height: size }}>
      {paths[name]}
    </svg>);

}

function ScoreSplit({ p, m, g, total, vizMode = "split" }) {
  if (p == null) {
    return <span className="mono faint" style={{ fontSize: 11 }}>—</span>;
  }
  if (vizMode === "radial") {
    const r = 18,c = 2 * Math.PI * r;
    const pf = p / 33 * (c / 3);
    const mf = m / 33 * (c / 3);
    const gf = g / 34 * (c / 3);
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <svg width="44" height="44" viewBox="0 0 44 44" style={{ transform: "rotate(-90deg)" }}>
          <circle cx="22" cy="22" r={r} fill="none" stroke="var(--bg-sunken)" strokeWidth="4" />
          <circle cx="22" cy="22" r={r} fill="none" stroke="var(--persist)" strokeWidth="4"
          strokeDasharray={`${pf} ${c - pf}`} strokeDashoffset="0" />
          <circle cx="22" cy="22" r={r} fill="none" stroke="var(--maturation)" strokeWidth="4"
          strokeDasharray={`${mf} ${c - mf}`} strokeDashoffset={-c / 3} />
          <circle cx="22" cy="22" r={r} fill="none" stroke="var(--gap)" strokeWidth="4"
          strokeDasharray={`${gf} ${c - gf}`} strokeDashoffset={-2 * c / 3} />
        </svg>
        <span className="score-num">{total}</span>
      </div>);

  }
  if (vizMode === "stacked") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 110 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="mono" style={{ fontSize: 9, color: "var(--fg-faint)", width: 8 }}>P</span>
          <div className="score-bar" style={{ height: 3 }}>
            <span className="seg-p" style={{ width: `${p / 33 * 100}%` }} />
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="mono" style={{ fontSize: 9, color: "var(--fg-faint)", width: 8 }}>M</span>
          <div className="score-bar" style={{ height: 3 }}>
            <span className="seg-m" style={{ width: `${m / 33 * 100}%` }} />
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="mono" style={{ fontSize: 9, color: "var(--fg-faint)", width: 8 }}>G</span>
          <div className="score-bar" style={{ height: 3 }}>
            <span className="seg-g" style={{ width: `${g / 34 * 100}%` }} />
          </div>
        </div>
      </div>);

  }
  // default: split
  return (
    <div className="score-split">
      <span className="score-num">{total}</span>
      <div className="score-bar" title={`P ${p} · M ${m} · G ${g}`}>
        <span className="seg-p" style={{ width: `${p / 100 * 100}%` }} />
        <span className="seg-m" style={{ width: `${m / 100 * 100}%` }} />
        <span className="seg-g" style={{ width: `${g / 100 * 100}%` }} />
      </div>
    </div>);

}

function ScoreCellWithTooltip({ p, m, g, total, vizMode }) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const ref = useRef();

  function onEnter() {
    if (ref.current) {
      const r = ref.current.getBoundingClientRect();
      setPos({ x: r.left, y: r.bottom + 6 });
    }
    setShow(true);
  }
  return (
    <span ref={ref} onMouseEnter={onEnter} onMouseLeave={() => setShow(false)} style={{ display: "inline-block", position: "relative" }}>
      <ScoreSplit p={p} m={m} g={g} total={total} vizMode={vizMode} />
      {show && p != null &&
      <div className="tt show" style={{ position: "fixed", left: pos.x, top: pos.y }}>
          <div className="head">Deep Info Score · {total}/100</div>
          <div className="row"><span className="l"><span className="seg-dot" style={{ background: "var(--persist)" }} />Persistence</span><span className="v">{p}/33</span></div>
          <div className="row"><span className="l"><span className="seg-dot" style={{ background: "var(--maturation)" }} />Maturation</span><span className="v">{m}/33</span></div>
          <div className="row"><span className="l"><span className="seg-dot" style={{ background: "var(--gap)" }} />Gap</span><span className="v">{g}/34</span></div>
        </div>
      }
    </span>);

}

function StateBadge({ state }) {
  const map = {
    RECOMMENDED: ["badge-recommended", "recommended"],
    ACTIVE: ["badge-active", "active"],
    MATURE: ["badge-mature", "mature"],
    WATCHING: ["badge-watching", "watching"],
    DEPRIORITIZED: ["badge-deprioritized", "deprioritized"],
    FORMING: ["badge-forming", "forming"],
    ARCHIVED: ["badge-archived", "archived"],
    OK: ["badge-ok", "ok"],
    FAILING: ["badge-failing", "failing"],
    DEAD: ["badge-dead", "dead"]
  };
  const [cls, label] = map[state] || ["badge-watching", state.toLowerCase()];
  return <span className={`badge ${cls}`}>{label}</span>;
}

function Sparkbar({ data, accent = false }) {
  if (!data || !data.length) return null;
  const max = Math.max(...data, 1);
  return (
    <div className={`sparkbar ${accent ? "accent" : ""}`} style={{ height: 18, width: 80 }}>
      {data.map((v, i) =>
      <span key={i} className={i === data.length - 1 ? "now" : ""} style={{ height: `${v / max * 100}%` }} />
      )}
    </div>);

}

function Sidebar({ page, setPage, selectedDesk, setSelectedDesk }) {
  const desks = [
    { id: "politik", label: "Politik", count: 4 },
    { id: "lingkungan", label: "Lingkungan", count: 2 },
    { id: "hukum", label: "Hukum", count: 2 },
    { id: "ekonomi", label: "Ekonomi", count: 4 },
    { id: "tokoh", label: "Tokoh", count: 3 },
    { id: "investigasi", label: "Investigasi", count: 0 },
    { id: "umum", label: "Umum", count: 1 },
  ];
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">C</div>
        <div>
          <div className="brand-name">Content Intelligence</div>
          <div className="brand-meta">v1.0 · prod</div>
        </div>
      </div>

      <div className="nav-group">
        <div className="nav-label">Workspace</div>
        <div className={`nav-item ${page === "dashboard" ? "active" : ""}`} onClick={() => setPage("dashboard")}>
          <Icon name="home" /> Dashboard
        </div>
        <div className={`nav-item ${page === "queue" ? "active" : ""}`} onClick={() => setPage("queue")}>
          <Icon name="inbox" /> Angle Queue
          <span className="count">23</span>
        </div>
        <div className={`nav-item ${page === "buckets" ? "active" : ""}`} onClick={() => setPage("buckets")}>
          <Icon name="layers" /> Topic Buckets
          <span className="count">142</span>
        </div>
        <div className={`nav-item ${page === "keywords" ? "active" : ""}`} onClick={() => setPage("keywords")}>
          <Icon name="trending" /> Keywords
        </div>
        <div className={`nav-item ${page === "performance" ? "active" : ""}`} onClick={() => setPage("performance")}>
          <Icon name="chart" /> Performance
        </div>
      </div>

      <div className="nav-group">
        <div className="nav-label">Desks</div>
        {desks.map(d => (
          <div
            key={d.id}
            className={`nav-item nav-desk ${page === "desk" && selectedDesk === d.id ? "active" : ""}`}
            onClick={() => { setSelectedDesk && setSelectedDesk(d.id); setPage("desk"); }}
          >
            <span className={`desk-dot desk-dot-${d.id}`}></span> {d.label}
            <span className="count">{d.count}</span>
          </div>
        ))}
      </div>

      <div className="nav-group">
        <div className="nav-label">Pipeline</div>
        <div className="nav-item">
          <Icon name="rss" /> Feeds
          <span className="dot" title="1 dead, 1 failing"></span>
        </div>
        <div className="nav-item">
          <Icon name="activity" /> Runs
        </div>
        <div className="nav-item">
          <Icon name="settings" /> Configuration
        </div>
      </div>

      <div className="sidebar-foot">
        <div className="user-chip">
          <div className="avatar">MS</div>
          <div>
            <div className="user-name">Maulana Shendi</div>
            <div className="user-role">Editor, Investigasi</div>
          </div>
        </div>
      </div>
    </aside>);

}

function StatusBar() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 4000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="statusbar">
      <div className="item">
        <span className="pulse"></span>
        <strong>operational</strong>
      </div>
      <div className="sep" />
      <div className="item"><strong>4,812</strong><span>articles</span></div>
      <div className="sep" />
      <div className="item"><strong>142</strong><span>buckets</span></div>
      <div className="sep" />
      <div className="item"><strong style={{ color: "var(--accent-fg)" }}>14</strong><span>recommended</span></div>
      <div className="grow" />
      <div className="item"><span>next ingest</span><strong>20:32</strong></div>
      <div className="sep" />
      <div className="item alert">
        <span className="pulse"></span>
        <span>1 feed dead</span>
      </div>
      <div className="sep" />
      <div className="item">
        <Icon name="bell" size={11} />
        <span>3</span>
      </div>
    </div>);

}

Object.assign(window, { Icon, ScoreSplit, ScoreCellWithTooltip, StateBadge, Sparkbar, Sidebar, StatusBar });