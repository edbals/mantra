// IDX Screener — main app shell with sidebar nav, top bar and view routing.
const { useState: useStateA, useEffect: useEffectA, useRef: useRefA } = React;

const NAV = [
  { id:"dashboard",  label:"Watchlist",      icon:IconDashboard },
  { id:"ticker",     label:"Ticker detail",  icon:IconScreener  },
  { id:"anomalies",  label:"IF Insights",    icon:IconAI        },
  { id:"analytics",  label:"Analytics",      icon:IconAnalytics, disabled:true },
  { id:"brokers",    label:"Broker explorer",icon:IconBroker,    disabled:true },
  { id:"settings",   label:"Settings",       icon:IconSettings,  disabled:true },
];

const App = () => {
  const [view, setView]       = useStateA("dashboard");
  const [ticker, setTicker]   = useStateA("MDIA");
  const [collapsed, setColl]  = useStateA(false);
  const [search, setSearch]   = useStateA("");
  const searchRef             = useRefA(null);

  useEffectA(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current && searchRef.current.focus();
      }
      if (e.key === "Escape" && document.activeElement === searchRef.current) {
        searchRef.current.blur();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`} style={{ height:"100%" }}>
      <div className="topbar">
        <div className="brand">
          <PixelM size={26}/>
          <div className="brand-name">Mantra <span>· IDX Screener</span></div>
        </div>
        <div className="search">
          <IconSearch w={14}/>
          <input
            ref={searchRef}
            placeholder="Search ticker or company…"
            value={search}
            onChange={(e)=>{ setSearch(e.target.value); setView("dashboard"); }}
          />
          <span className="kbd">⌘K</span>
        </div>
        <div className="topbar-right">
          <span className="pill"><span className="live-dot"/> Updated on {window.SCORING_DATE || "—"}</span>
          <button className="btn" title="Refresh" onClick={()=>window.parent && window.parent.location.reload()}>
            <IconRefresh w={13}/>
          </button>
        </div>
      </div>

      <div className="sidebar">
        <button className="nav-item" onClick={()=>setColl(!collapsed)} style={{ marginBottom:6 }}>
          <span className="nav-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M3 12h18M3 6h18M3 18h18"/>
            </svg>
          </span>
          <span className="nav-label" style={{ fontSize:12, color:"var(--text-3)" }}>Collapse</span>
        </button>
        <div className="sidebar-section-title">Workspace</div>
        <div className="nav">
          {NAV.slice(0,3).map(n => (
            <button key={n.id}
              className={`nav-item ${view===n.id?"active":""}`}
              onClick={()=>!n.disabled && setView(n.id)}
              style={{ opacity: n.disabled?0.45:1 }}>
              <span className="nav-icon"><n.icon w={16}/></span>
              <span className="nav-label">{n.label}</span>
            </button>
          ))}
        </div>
        <div className="sidebar-section-title">Tools</div>
        <div className="nav">
          {NAV.slice(3).map(n => (
            <button key={n.id}
              className={`nav-item ${view===n.id?"active":""}`}
              onClick={()=>!n.disabled && setView(n.id)}
              style={{ opacity: n.disabled?0.45:1 }}>
              <span className="nav-icon"><n.icon w={16}/></span>
              <span className="nav-label">{n.label}</span>
              {n.disabled && <span className="nav-label" style={{ marginLeft:"auto", fontSize:10, color:"var(--text-4)" }}>Soon</span>}
            </button>
          ))}
        </div>
        <div className="sidebar-spacer"/>
      </div>

      <div className="main">
        {view === "dashboard"  && <DashboardView
          search={search}
          onPickTicker={(t)=>{setTicker(t); setView("ticker"); }}
          onViewReport={()=>setView("anomalies")}/>}
        {view === "ticker"     && <TickerView     ticker={ticker} setTicker={setTicker}/>}
        {view === "anomalies"  && <AnomaliesView onPickTicker={(t)=>{setTicker(t); setView("ticker"); }}/>}
      </div>
    </div>
  );
};

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
