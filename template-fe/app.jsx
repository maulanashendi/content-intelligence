// Main app
const { useState } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "scoreViz": "split"
} /*EDITMODE-END*/;

function App() {
  const [page, setPage] = useState("dashboard");
  const [selectedBucket, setSelectedBucket] = useState(1);
  const [selectedDesk, setSelectedDesk] = useState("politik");
  const [tweaks, setTweaks] = window.useTweaks ? window.useTweaks(TWEAK_DEFAULTS) : [TWEAK_DEFAULTS, () => {}];
  const vizMode = tweaks.scoreViz || "split";

  const titles = {
    dashboard: { t: <>Dashboard <span className="serif italic">·</span> editorial intelligence</>, s: "Live signal across 12 feeds, 142 active topic buckets, and the angle queue. Updated every 6 hours; live where it matters." },
    queue: { t: <>Competitor Insights <span className="serif italic">·</span> by bucket</>, s: "What other outlets have published on each top bucket — and where the gaps remain. Captured every cluster cycle." },
    buckets: { t: <>Topic Buckets <span className="serif italic">·</span> all clusters</>, s: "Semantic clusters of articles in the rolling 14-day window. Sort by score, filter by state." },
    bucket: { t: "Topic Bucket", s: "" },
    desk: { t: "Desk Insight", s: "" },
    keywords: { t: <>Keywords <span className="serif italic">·</span> rising signals</>, s: "Composite ranking from RSS frequency, Google Trends, and GSC impressions." },
    performance: { t: <>Performance <span className="serif italic">·</span> attribution report</>, s: "From recommendation to publication. Closing the editorial loop." }
  };

  const title = titles[page] || titles.dashboard;

  return (
    <div className="app">
      <Sidebar page={page} setPage={setPage} selectedDesk={selectedDesk} setSelectedDesk={setSelectedDesk} />
      <main className="main">
        <StatusBar />
        {page !== "bucket" && page !== "desk" &&
        <div className="page-head">
            <div>
              <h1 className="page-title">{title.t}</h1>
              <p className="page-sub">{title.s}</p>
            </div>
            <div className="page-actions">
              <button className="btn"><Icon name="refresh" size={12} />Refresh<span className="kbd">R</span></button>
              <button className="btn"><Icon name="filter" size={12} />Filter</button>
              <button className="btn btn-primary"><Icon name="plus" size={12} />Submit</button>
            </div>
          </div>
        }
        {page === "dashboard" && <Dashboard vizMode={vizMode} setPage={setPage} setSelectedBucket={setSelectedBucket} setSelectedDesk={setSelectedDesk} />}
        {page === "queue" && <AngleQueue />}
        {page === "buckets" && <BucketsPage setSelectedBucket={setSelectedBucket} setPage={setPage} vizMode={vizMode} setSelectedDesk={setSelectedDesk} />}
        {page === "bucket" && <BucketDetail bucketId={selectedBucket} setPage={setPage} vizMode={vizMode} />}
        {page === "desk" && <DeskInsight desk={selectedDesk} setSelectedBucket={setSelectedBucket} setPage={setPage} />}
        {page === "keywords" && <KeywordsPage />}
        {page === "performance" && <Performance />}
      </main>

      {window.TweaksPanel &&
      <window.TweaksPanel title="Tweaks">
          <window.TweakSection title="Score Visualization">
            <window.TweakRadio
            label="Score viz style"
            value={vizMode}
            options={[
            { label: "Split bar (P/M/G stacked)", value: "split" },
            { label: "Stacked mini bars", value: "stacked" },
            { label: "Radial donut", value: "radial" }]
            }
            onChange={(v) => setTweaks({ scoreViz: v })} />
          
          </window.TweakSection>
        </window.TweaksPanel>
      }
    </div>);

}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);