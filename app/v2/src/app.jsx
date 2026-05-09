// IDX Screener — main app shell with sidebar nav, top bar and view routing.
// Tweaks panel removed for embedded Streamlit hosting.
const { useState: useStateA, useEffect: useEffectA } = React;

const NAV = [
  { id:"dashboard",  label:"Watchlist",      icon:IconDashboard },
  { id:"ticker",     label:"Ticker detail",  icon:IconScreener  },
  { id:"anomalies",  label:"AI Insights",    icon:IconAI        },
  { id:"analytics",  label:"Analytics",      icon:IconAnalytics, disabled:true },
  { id:"brokers",    label:"Broker explorer",icon:IconBroker,    disabled:true },
  { id:"settings",   label:"Settings",       icon:IconSettings,  disabled:true },
];

const App = () => {
  const [view, setView]       = useStateA("dashboard");
  const [ticker, setTicker]   = useStateA("MDIA");
  const [collapsed, setColl]  = useStateA(false);

  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`} style={{ height:"100%" }}>
      <div className="topbar">
        <div className="brand">
          <div className="brand-mark"/>
          <div className="brand-name">MyMantra <span>· IDX Screener</span></div>
        </div>
        <div className="search">
          <IconSearch w={14}/>
          <input placeholder="Search ticker, company, sector…"/>
          <span className="kbd">⌘K</span>
        </div>
        <div className="topbar-right">
          <span className="pill"><span className="live-dot"/> Live · IDX feed</span>
          <button className="icon-btn" title="Notifications" style={{ position:"relative" }}>
            <IconBell w={15}/>
            <span style={{ position:"absolute", top:4, right:4, width:6, height:6, borderRadius:999, background:"var(--red)" }}/>
          </button>
          <button className="btn" title="Refresh"><IconRefresh w={13}/></button>
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
        <div className="sidebar-footer">
          <div className="avatar">YK</div>
          <div className="sidebar-footer-text" style={{ display:"flex", flexDirection:"column" }}>
            <span style={{ color:"var(--text-2)", fontSize:12 }}>You · analyst</span>
            <span style={{ color:"var(--text-4)", fontSize:11 }}>Updated 12:04 WIB</span>
          </div>
        </div>
      </div>

      <div className="main">
        {view === "dashboard"  && <DashboardView
          onPickTicker={(t)=>{setTicker(t); setView("ticker"); }}
          onViewReport={()=>setView("anomalies")}/>}
        {view === "ticker"     && <TickerView     ticker={ticker} setTicker={setTicker}/>}
        {view === "anomalies"  && <AnomaliesView/>}
      </div>
    </div>
  );
};

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
