// View components for IDX Screener prototype
const { useState: useStateV, useEffect: useEffectV, useRef: useRefV } = React;

// ── Calendar popover — real month grid, not a select ───────────────────
const Calendar = ({ value, available = [], onPick }) => {
  const [open, setOpen] = useStateV(false);
  const initial = value ? new Date(value + "T00:00:00") : new Date();
  const [view, setView] = useStateV(initial);
  const ref = useRefV(null);

  useEffectV(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const year  = view.getFullYear();
  const month = view.getMonth();
  const monthName = view.toLocaleString("en-US", { month: "long" });
  const firstDOW = (new Date(year, month, 1).getDay() + 6) % 7;   // Mon=0..Sun=6
  const daysIn = new Date(year, month + 1, 0).getDate();
  const cells = Array.from({ length: firstDOW }, () => null)
                     .concat(Array.from({ length: daysIn }, (_, i) => i + 1));
  const fmt = (d) => `${year}-${String(month+1).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
  const avail = new Set(available);

  return (
    <div ref={ref} style={{ position:"relative" }}>
      <button className="btn" onClick={()=>setOpen(!open)}>
        <IconCalendar w={13}/> {value || "Select date"}
      </button>
      {open && (
        <div style={{
          position:"absolute", top:"calc(100% + 6px)", right:0, zIndex:200, width:268,
          background:"var(--surface-1)", border:"1px solid var(--line-2)",
          borderRadius:10, padding:14, boxShadow:"0 14px 38px rgba(0,0,0,.55)",
        }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10 }}>
            <button className="icon-btn" title="Previous month"
              onClick={()=>setView(new Date(year, month - 1, 1))}>‹</button>
            <span style={{ fontWeight:600, fontSize:13 }}>{monthName} {year}</span>
            <button className="icon-btn" title="Next month"
              onClick={()=>setView(new Date(year, month + 1, 1))}>›</button>
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(7, 1fr)", gap:4,
                        fontSize:10, color:"var(--text-3)", textAlign:"center", marginBottom:4,
                        textTransform:"uppercase", letterSpacing:"0.06em" }}>
            {["Mo","Tu","We","Th","Fr","Sa","Su"].map((d,i)=> <div key={i}>{d}</div>)}
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(7, 1fr)", gap:4 }}>
            {cells.map((d,i) => {
              if (!d) return <div key={i}/>;
              const ds = fmt(d);
              const has = avail.has(ds);
              const isSel = ds === value;
              const cellStyle = {
                display:"flex", alignItems:"center", justifyContent:"center",
                height:32, fontSize:12,
                fontFamily:"var(--mono)", fontVariantNumeric:"tabular-nums",
                color:  isSel ? "#06181a" : has ? "var(--text)" : "var(--text-4)",
                background: isSel ? "var(--accent)" : has ? "oklch(1 0 0 / 0.04)" : "transparent",
                border: isSel ? "1px solid var(--accent)" : "1px solid transparent",
                borderRadius: 6,
                cursor: has ? "pointer" : "default",
                fontWeight: has ? 600 : 400,
                opacity: has ? 1 : 0.35,
                textDecoration:"none",
                userSelect:"none",
              };
              if (!has) return <div key={i} style={cellStyle}>{d}</div>;
              // Native <a target="_top"> escapes the iframe sandbox reliably
              return (
                <a key={i} href={`?date=${ds}`} target="_top" style={cellStyle}
                   onClick={()=>setOpen(false)}>
                  {d}
                </a>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
const D = window.IDX_DATA || {};
// Guarantee every key exists so an unexpected null doesn't crash a render
D.RANKINGS         = D.RANKINGS         || [];
D.SUBSCORES        = D.SUBSCORES        || {};
D.FLOW_SIGNALS     = D.FLOW_SIGNALS     || [];
D.TOP_BUYERS       = D.TOP_BUYERS       || [];
D.TOP_SELLERS      = D.TOP_SELLERS      || [];
D.BROKER_NET       = D.BROKER_NET       || [];
D.PRICE_SERIES     = D.PRICE_SERIES     || [];
D.SCORE_HISTORY    = D.SCORE_HISTORY    || [];
D.ANOMALIES        = D.ANOMALIES        || [];
D.ISOLATION_FOREST = D.ISOLATION_FOREST || [];

const KPI = ({ label, value, unit, color }) => (
  <div className="kpi">
    <div className="kpi-label">{label}</div>
    <div className="kpi-row">
      <span className="kpi-value" style={{ color: color || "var(--text)" }}>{value}</span>
      {unit && <span className="kpi-unit">{unit}</span>}
    </div>
  </div>
);

const DashboardView = ({ search = "", onPickTicker, onViewReport }) => {
  const [filter, setFilter]     = useStateV("ALL");
  const [breakout, setBreakout] = useStateV(false);
  const [minAdvB, setMinAdvB]   = useStateV(0);
  const [sortKey, setSortKey]   = useStateV("rank");
  const [sortDir, setSortDir]   = useStateV("asc");

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir(key === "rank" || key === "ticker" ? "asc" : "desc"); }
  };

  const q = search.trim().toLowerCase();
  const filtered = D.RANKINGS.filter(r => {
    if (filter !== "ALL" && r.action !== filter) return false;
    if (breakout && !r.breakout) return false;
    if (r.advB < minAdvB) return false;
    if (q && !r.ticker.toLowerCase().includes(q) && !r.name.toLowerCase().includes(q)) return false;
    return true;
  });
  const rows = [...filtered].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (av === bv) return 0;
    if (typeof av === "string") return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortDir === "asc" ? (av - bv) : (bv - av);
  });

  const SortHeader = ({ k, label, className = "" }) => (
    <th className={`sortable ${className}`} onClick={()=>toggleSort(k)}>
      {label}{sortKey === k && <span className="sort-arrow">{sortDir === "asc" ? "▲" : "▼"}</span>}
    </th>
  );

  const kpis = [
    { label:"Invest signals", value: D.RANKINGS.filter(r=>r.action==="INVEST").length, unit:"", delta:{ v:"+2", up:true,  hint:"vs yesterday" }, color:"var(--green)",  icon:<IconCheck w={14}/> },
    { label:"Watch / Exec",   value: D.RANKINGS.filter(r=>r.action==="WATCH_EXEC").length, unit:"", delta:{ v:"−1", up:false, hint:"vs yesterday" }, color:"var(--amber)",  icon:<IconBookmark w={14}/> },
    { label:"Avg score",      value: (D.RANKINGS.reduce((a,r)=>a+r.score,0)/D.RANKINGS.length).toFixed(1), unit:"/100", delta:{ v:"+2.1", up:true, hint:"today" }, color:"var(--accent)", icon:<IconChartBar w={14}/> },
    { label:"Anomaly alerts", value: 5, unit:"high", delta:{ v:"2 mod", up:false, hint:"≥ 50 IF" }, color:"var(--red)", icon:<IconAnomaly w={14}/> },
  ];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Dashboard · IDX</div>
          <div className="h1">Watchlist · 100 candidates</div>
          <div className="subtitle">Top scored by broker flow signal · scored {new Date().toDateString()}</div>
        </div>
        <div style={{ display:"flex", gap:8 }}>
          <span className="btn" style={{ cursor:"default" }}>
            <IconCalendar w={13}/> {window.SCORING_DATE || "—"}
          </span>
          <button className="btn-primary btn" onClick={()=>window.parent && window.parent.location.reload()}>
            <IconRefresh w={13}/> Refresh data
          </button>
        </div>
      </div>

      <div className="kpi-grid">
        {kpis.map(k => (
          <div key={k.label} className="kpi">
            <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
              <div className="kpi-label">{k.label}</div>
              <span style={{ color: k.color }}>{k.icon}</span>
            </div>
            <div className="kpi-row">
              <span className="kpi-value" style={{ color: k.color }}>{k.value}</span>
              {k.unit && <span className="kpi-unit">{k.unit}</span>}
            </div>
            <div className="kpi-delta">
              <span className={k.delta.up ? "up" : "down"}>
                {k.delta.up ? <IconArrowUp w={11} s={2.4}/> : <IconArrowDown w={11} s={2.4}/>} {k.delta.v}
              </span>
              <span className="dim">{k.delta.hint}</span>
            </div>
            <div className="spark">
              <Sparkline data={[3,5,4,8,6,9,7,10,8,12]} w={70} h={22} color={k.color}/>
            </div>
          </div>
        ))}
      </div>

      <div className="ai-banner">
        <span className="ai-spark"><IconBolt w={16} s={2}/></span>
        <div style={{ flex:1 }}>
          <div className="ai-banner-title">
            <strong>AI Insights</strong>
            <span style={{ display:"inline-flex", alignItems:"center", gap:6, padding:"1px 8px", borderRadius:4, background:"oklch(0.72 0.14 192 / 0.12)", color:"var(--accent)", fontSize:10.5, letterSpacing:"0.1em" }}>
              <span className="live-dot" style={{ width:5, height:5, background:"var(--accent)", boxShadow:"0 0 6px var(--accent)" }}/> LIVE
            </span>
          </div>
          <div className="ai-banner-text" style={{ marginTop:6 }}
            dangerouslySetInnerHTML={{ __html: window.AI_INSIGHTS ||
              "<b>3 tickers</b> show extreme broker anomaly scores (&gt;70). Institutional absorption detected in <b>MEDS</b>, <b>GOTO</b>, <b>MAPI</b>. <b>XL/XC retail divergence</b> confirmed across 7 tickers in the low-float segment."
            }}/>
        </div>
        <button className="btn" onClick={()=>onViewReport && onViewReport()}>View report</button>
      </div>

      <Card
        title="Rankings"
        subtitle="Top 100 by broker signal strength · scored with real broker flow data"
        actions={
          <div className="filterbar" style={{ margin:0 }}>
            {["ALL","INVEST","WATCH_EXEC","WATCH","OBSERVE"].map(f => (
              <button key={f} className={`chip ${filter===f?"active":""}`} onClick={()=>setFilter(f)}>{f.replace("_"," ")}</button>
            ))}
            <button className={`chip ${breakout?"active":""}`} onClick={()=>setBreakout(!breakout)}>
              <IconBolt w={11}/> Breakout only
            </button>
            <span className="range-chip">
              Min ADV
              <input type="range" min="0" max="100" step="1" value={minAdvB} onChange={e=>setMinAdvB(+e.target.value)}/>
              <span className="mono" style={{ width:36, textAlign:"right" }}>{minAdvB}B</span>
            </span>
          </div>
        }
      >
        <div style={{ overflow:"auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <SortHeader k="rank"          label="#"/>
                <SortHeader k="ticker"        label="Ticker"/>
                <SortHeader k="name"          label="Company"/>
                <SortHeader k="action"        label="Action"/>
                <SortHeader k="score"         label="Score"          className="num right"/>
                <SortHeader k="breakout"      label="Breakout"/>
                <SortHeader k="brokerFlow"    label="Broker flow"    className="num"/>
                <SortHeader k="floatPressure" label="Float pressure" className="num"/>
                <SortHeader k="anomaly"       label="Anomaly"        className="num"/>
                <SortHeader k="xlxc"          label="XL / XC"/>
                <SortHeader k="close"         label="Close (IDR)"    className="num right"/>
                <SortHeader k="advB"          label="ADV (B)"        className="num right"/>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.ticker}
                    className={r.action==="INVEST" ? "invest" : ""}
                    onClick={()=>onPickTicker && onPickTicker(r.ticker)}
                    style={{ cursor: onPickTicker ? "pointer" : "default" }}>
                  <td className="rank-cell">{String(r.rank).padStart(2,"0")}</td>
                  <td className="ticker-cell">{r.ticker} <TrendArrow v={r.trend}/></td>
                  <td className="company-cell">{r.name}</td>
                  <td><Badge label={r.action}/></td>
                  <td className="right"><ScoreMini v={r.score}/></td>
                  <td>{r.breakout ?
                    <span style={{ display:"inline-flex", alignItems:"center", gap:6, color:"var(--accent)", fontFamily:"var(--mono)", fontSize:11 }}>
                      <IconBolt w={11} s={2}/> Yes
                    </span>
                    : <span className="dim mono" style={{ fontSize:11 }}>—</span>}</td>
                  <td><SparkBar v={r.brokerFlow} color={colorForSub(r.brokerFlow)}/></td>
                  <td><SparkBar v={r.floatPressure} color={colorForSub(r.floatPressure)}/></td>
                  <td><AnomalyTag v={r.anomaly}/></td>
                  <td><XLXC v={r.xlxc}/></td>
                  <td className="right num">{r.close.toLocaleString()}</td>
                  <td className="right num">{r.advB.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

const TickerHero = ({ ticker }) => {
  const r = D.RANKINGS.find(x => x.ticker === ticker) || D.RANKINGS[0];
  return (
    <div className="ticker-hero">
      <div>
        <div className="symbol">{r.ticker}</div>
        <div className="company">{r.name}</div>
      </div>
      <div style={{ marginLeft:"auto", display:"flex", gap:24, alignItems:"center" }}>
        <div className="hero-stat" style={{ alignItems:"flex-start" }}><Badge label={r.action}/></div>
        <div className="hero-stat"><span className="label">Invest</span><span className="val amber">{r.score.toFixed(1)}</span></div>
        <div className="hero-stat"><span className="label">Breakout</span><span className={`val ${r.breakout?"":"dim"}`}>{r.breakout ? "Yes" : "—"}</span></div>
        <div className="hero-stat"><span className="label">Close (IDR)</span><span className="val">{r.close.toLocaleString()}</span></div>
        <div className="hero-stat"><span className="label">ADV (B IDR)</span><span className="val">{r.advB.toFixed(1)}</span></div>
      </div>
    </div>
  );
};

const ScoresTab = ({ ticker }) => {
  const r = D.RANKINGS.find(x => x.ticker === ticker) || D.RANKINGS[0];
  const liq = Math.round(35 + (r.advB / 600) * 60);
  const str = Math.round(40 + (r.score - 30) * 0.5);
  const subs = {
    bf:  { label:"Broker flow",    val: r.brokerFlow,    weight: 0.40 },
    fp:  { label:"Float pressure", val: r.floatPressure, weight: 0.30 },
    liq: { label:"Liquidity",      val: Math.max(20, Math.min(95, liq)), weight: 0.20 },
    str: { label:"Structure",      val: Math.max(20, Math.min(95, str)), weight: 0.10 },
  };
  return (
    <div style={{ display:"grid", gridTemplateColumns:"1.4fr 1fr", gap:16 }}>
      <Card title="Investment sub-scores" subtitle="Weighted contribution to overall investment score">
        <div style={{ padding:"6px 18px 18px" }}>
          <div style={{ display:"flex", gap:18, alignItems:"center", padding:"14px 0", borderBottom:"1px solid var(--line)" }}>
            <ScoreWheel value={r.score} label="overall" sub="overall" size={120}/>
            <div>
              <div style={{ fontSize:11, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.1em" }}>Composite</div>
              <div style={{ fontFamily:"var(--mono)", fontSize:30, fontWeight:600, marginTop:2 }}>{r.score.toFixed(1)} <span style={{ color:"var(--text-3)", fontSize:14 }}>/ 100</span></div>
              <div style={{ display:"flex", gap:18, marginTop:10 }}>
                <div style={{ fontSize:12, color:"var(--text-3)" }}>Weights:</div>
                <div style={{ display:"flex", gap:10, fontSize:11.5, fontFamily:"var(--mono)" }}>
                  <span>BF×0.40</span><span>FP×0.30</span><span>LIQ×0.20</span><span>STR×0.10</span>
                </div>
              </div>
            </div>
          </div>
          {Object.entries(subs).map(([k,s]) => (
            <div className="sub-row" key={k}>
              <div className="meta">
                <div className="label">{s.label} <span className="weight">×{s.weight.toFixed(2)}</span></div>
              </div>
              <div className="bar-wrap">
                <div className="bar-track">
                  <div className="bar-fill" style={{ width:`${s.val}%`, background: colorForSub(s.val) }}/>
                  <div className="ticks">
                    {[25,50,75].map(t => <i key={t} style={{ left: `${t}%` }}/>)}
                  </div>
                </div>
              </div>
              <div className="num" style={{ color: colorForSub(s.val) }}>{s.val.toFixed(1)}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Real broker flow signals" subtitle="Live institutional vs retail divergence">
        <div style={{ padding:"14px 18px 18px" }} className="flow-signals">
          {D.FLOW_SIGNALS.map((s,i) => (
            <div key={i} className="flow-signal">
              <div className="flow-signal-head">
                <div className="name">{s.label}</div>
                <div className={`v ${s.tone}`}>
                  {s.tone === "green" && <span style={{ marginRight:4 }}><IconBolt w={11} s={2.2}/></span>}
                  {s.value}
                </div>
              </div>
              <div className="desc">{s.desc}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

const BrokerTab = ({ ticker }) => {
  const buyPct = 37, sellPct = 63;
  const brokerIF = (D.BROKER_IF_BY_TICKER && D.BROKER_IF_BY_TICKER[ticker]) || [];
  // Build broker name lookup from the IF data so net-volume bars can show names
  const brokerNames = {};
  brokerIF.forEach(b => { brokerNames[b.code] = b.name; });
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:14 }}>
        <KPI label="Institutional net" value="−43.17M" unit="lots" color="var(--red)"/>
        <KPI label="Retail net"        value="+32.01M" unit="lots" color="var(--green)"/>
        <KPI label="Total volume"      value="988.7M"  unit="lots"/>
        <KPI label="Brokers active"    value="54"/>
      </div>

      <Card>
        <div style={{ padding:"18px 22px 6px" }}>
          <DistBar sellPct={sellPct} buyPct={buyPct}/>
        </div>
      </Card>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
        <Card title="Top buyers" subtitle="By buy volume">
          <div className="broker-list">
            {D.TOP_BUYERS.map(b => (
              <div key={b.code} className="b buy">
                <span className="code">{b.code}</span>
                <span className="name">{b.name}</span>
                <span className="vol">{b.buy.toFixed(2)}M</span>
                <span className={`net ${(b.buy-b.sell) >= 0 ? "pos":"neg"}`}>{(b.buy-b.sell) >= 0 ? "+":""}{(b.buy-b.sell).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Top sellers" subtitle="By sell volume">
          <div className="broker-list">
            {D.TOP_SELLERS.map(b => (
              <div key={b.code} className="b sell">
                <span className="code">{b.code}</span>
                <span className="name">{b.name}</span>
                <span className="vol">{b.sell.toFixed(2)}M</span>
                <span className={`net ${(b.buy-b.sell) >= 0 ? "pos":"neg"}`}>{(b.buy-b.sell) >= 0 ? "+":""}{(b.buy-b.sell).toFixed(2)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Net volume by broker" subtitle="Green = net buyer, red = net seller. Hover a bar to see the broker name.">
        <div style={{ padding:"6px 18px 8px" }}>
          <NetVolumeBars data={D.BROKER_NET} brokerNames={brokerNames}/>
        </div>
      </Card>

      {brokerIF.length > 0 && (
        <Card title={`Isolation Forest — broker anomalies for ${ticker}`}
              subtitle="Brokers whose activity on this ticker today is unusual vs their own history. Higher score = more anomalous.">
          <div style={{ overflow:"auto" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Broker</th>
                  <th className="num right">Z-score</th>
                  <th className="num right">IF score</th>
                  <th>Direction</th>
                </tr>
              </thead>
              <tbody>
                {brokerIF.map(b => (
                  <tr key={b.code}>
                    <td><span className="ticker-cell">{b.code}</span> <span className="muted2">— {b.name}</span></td>
                    <td className="right num" style={{ color: b.z>0 ? "var(--green)" : "var(--red)" }}>{b.z>0?"+":""}{b.z.toFixed(1)}</td>
                    <td className="right num"><AnomalyTag v={b.score}/></td>
                    <td><XLXC v={b.dir==="buying"?"net-buy":(b.dir==="selling"?"net-sell":"balance")}/></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};

const PriceTab = () => {
  const last = D.PRICE_SERIES[D.PRICE_SERIES.length - 1];
  const prevHigh = Math.max(...D.PRICE_SERIES.map(d=>d.close));
  const prevLow  = Math.min(...D.PRICE_SERIES.map(d=>d.close));
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      <Card title="Close & volume" subtitle="30-day price action with volume profile">
        <div style={{ padding:"6px 14px 14px" }}>
          <PriceVolumeChart data={D.PRICE_SERIES}/>
        </div>
      </Card>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:14 }}>
        <KPI label="Close"        value={last.close.toLocaleString()}/>
        <KPI label="Volume"       value={(last.volume/1e6).toFixed(0) + "M"}/>
        <KPI label="20-day high"  value={prevHigh.toLocaleString()}/>
        <KPI label="20-day low"   value={prevLow.toLocaleString()}/>
      </div>
    </div>
  );
};

const HistoryTab = () => (
  <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
    <Card title="Score history" subtitle="Investment score & broker flow over the last 12 sessions"
      actions={
        <div className="chart-legend">
          <span className="legend-swatch"><i style={{ background:"var(--accent)" }}/> Investment</span>
          <span className="legend-swatch"><i style={{ background:"var(--orange)" }}/> Broker flow</span>
        </div>
      }>
      <div style={{ padding:"6px 14px 16px" }}>
        <ScoreHistoryChart data={D.SCORE_HISTORY}/>
      </div>
    </Card>
    <Card title="Daily history">
      <div style={{ overflow:"auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Date</th><th>Action</th>
              <th className="num right">Investment score</th>
              <th className="num right">Broker flow score</th>
            </tr>
          </thead>
          <tbody>
            {[...D.SCORE_HISTORY].reverse().map(d => (
              <tr key={d.date}>
                <td className="mono">{d.date}</td>
                <td><Badge label={d.action}/></td>
                <td className="right num"><ScoreMini v={d.invest}/></td>
                <td className="right num"><SparkBar v={d.bf} color={colorForSub(d.bf)} w={70}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  </div>
);

const TickerView = ({ ticker, setTicker }) => {
  const [tab, setTab] = useStateV("scores");
  const tabs = [
    { id:"scores",  label:"Scores",          icon:<IconChartBar w={14}/> },
    { id:"broker",  label:"Broker analysis", icon:<IconBroker w={14}/> },
    { id:"price",   label:"Price & volume",  icon:<IconAnalytics w={14}/> },
    { id:"history", label:"History",         icon:<IconHistory w={14}/> },
  ];
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Ticker detail</div>
          <div className="h1">Deep dive · {ticker}</div>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          <span style={{ fontSize:12, color:"var(--text-3)" }}>Select ticker</span>
          <select className="btn" value={ticker} onChange={e=>setTicker(e.target.value)} style={{ padding:"6px 10px", minWidth:200 }}>
            {D.RANKINGS.map(r => <option key={r.ticker} value={r.ticker}>{r.ticker} · {r.name}</option>)}
          </select>
        </div>
      </div>

      <TickerHero ticker={ticker}/>

      <div className="tabs">
        {tabs.map(t => (
          <button key={t.id} className={`tab ${tab===t.id?"active":""}`} onClick={()=>setTab(t.id)}>
            <span className="tab-icon">{t.icon}</span> {t.label}
          </button>
        ))}
      </div>

      {tab === "scores"  && <ScoresTab ticker={ticker}/>}
      {tab === "broker"  && <BrokerTab ticker={ticker}/>}
      {tab === "price"   && <PriceTab/>}
      {tab === "history" && <HistoryTab/>}
    </div>
  );
};

const AnomaliesView = ({ onPickTicker }) => (
  <div className="page">
    <div className="page-head">
      <div>
        <div className="eyebrow">Isolation Forest Insights</div>
        <div className="h1">Volume anomalies today</div>
        <div className="subtitle">Stocks whose trading volume today is unusually different from their normal pattern over the last 22 trading days. Highlights stocks that may be moving on news or accumulation. Click any row to open the ticker.</div>
      </div>
      <div style={{ display:"flex", gap:10, alignItems:"flex-end" }}>
        <div>
          <div style={{ fontSize:11, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:4 }}>Baseline window</div>
          <select className="btn" defaultValue="22d" style={{ padding:"6px 10px", minWidth:140 }}>
            <option>1 month (22d)</option><option>2 weeks (10d)</option><option>3 months (66d)</option>
          </select>
        </div>
        <div>
          <div style={{ fontSize:11, color:"var(--text-3)", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:4 }}>Compare period</div>
          <select className="btn" defaultValue="today" style={{ padding:"6px 10px", minWidth:140 }}>
            <option>Today</option><option>This week</option><option>Custom…</option>
          </select>
        </div>
      </div>
    </div>

    <Card title="Flagged tickers · today" subtitle="Volume z-score outliers — Isolation Forest concurrence">
      <div style={{ overflow:"auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Ticker</th>
              <th className="num right">Volume today (M lots)</th>
              <th className="num right">Avg 22d (M lots)</th>
              <th className="num right">Z-score</th>
              <th className="num right">IF score</th>
              <th>Direction</th>
            </tr>
          </thead>
          <tbody>
            {D.ANOMALIES.length === 0 && (
              <tr><td colSpan="6" style={{ textAlign:"center", color:"var(--text-3)", padding:"22px" }}>
                No volume anomalies flagged today across the Stage 2 universe.
              </td></tr>
            )}
            {D.ANOMALIES.map(a => (
              <tr key={a.code}
                  onClick={()=>onPickTicker && onPickTicker(a.code)}
                  style={{ cursor: onPickTicker ? "pointer" : "default" }}>
                <td><span className="ticker-cell">{a.code}</span> <span className="muted2">— {a.name}</span></td>
                <td className="right num">{a.signal.toFixed(2)}</td>
                <td className="right num muted">{a.baseline.toFixed(2)}</td>
                <td className="right num" style={{ color: a.z>0 ? "var(--green)" : "var(--red)" }}>{a.z>0?"+":""}{a.z.toFixed(1)}</td>
                <td className="right num"><AnomalyTag v={Math.round(a.ifScore)}/></td>
                <td><XLXC v={a.dir==="buy"?"net-buy":"net-sell"}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>

    <div style={{ marginTop:16 }}/>

    <Card title="Isolation Forest — top tickers by volume anomaly" subtitle="IF score ≥ 50 moderate · ≥ 70 strong"
      actions={
        <div className="chart-legend">
          <span className="legend-swatch"><i style={{ background:"var(--green)" }}/> Buying</span>
          <span className="legend-swatch"><i style={{ background:"var(--red)" }}/> Selling</span>
        </div>
      }>
      <div style={{ padding:"8px 18px 8px" }}>
        <IsolationForest data={D.ISOLATION_FOREST}/>
      </div>
    </Card>
  </div>
);

Object.assign(window, { DashboardView, TickerView, AnomaliesView });
