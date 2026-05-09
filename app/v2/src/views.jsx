// View components for IDX Screener prototype
const { useState: useStateV } = React;
const D = window.IDX_DATA;

const KPI = ({ label, value, unit, color }) => (
  <div className="kpi">
    <div className="kpi-label">{label}</div>
    <div className="kpi-row">
      <span className="kpi-value" style={{ color: color || "var(--text)" }}>{value}</span>
      {unit && <span className="kpi-unit">{unit}</span>}
    </div>
  </div>
);

const DashboardView = ({ onPickTicker, onViewReport }) => {
  const [filter, setFilter]     = useStateV("ALL");
  const [breakout, setBreakout] = useStateV(false);
  const [minScore, setMinScore] = useStateV(0);
  const [minAdvB, setMinAdvB]   = useStateV(0);

  const rows = D.RANKINGS.filter(r => {
    if (filter !== "ALL" && r.action !== filter) return false;
    if (breakout && !r.breakout) return false;
    if (r.score < minScore) return false;
    if (r.advB < minAdvB) return false;
    return true;
  });

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
          <span className="btn" style={{ cursor:"default" }}><IconCalendar w={13}/> {window.SCORING_DATE || "—"}</span>
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
              Min score
              <input type="range" min="0" max="80" value={minScore} onChange={e=>setMinScore(+e.target.value)}/>
              <span className="mono" style={{ width:24, textAlign:"right" }}>{minScore}</span>
            </span>
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
                <th>#</th><th>Ticker</th><th>Company</th><th>Action</th>
                <th className="num right">Score</th><th>Breakout</th>
                <th className="num">Broker flow</th><th className="num">Float pressure</th>
                <th className="num">Anomaly</th><th>XL / XC</th>
                <th className="num right">Close (IDR)</th><th className="num right">ADV (B)</th>
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

const BrokerTab = () => {
  const buyPct = 37, sellPct = 63;
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

      <Card title="Net volume by broker" subtitle="Green = net buyer, Red = net seller">
        <div style={{ padding:"6px 18px 8px" }}>
          <NetVolumeBars data={D.BROKER_NET}/>
        </div>
      </Card>
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
      {tab === "broker"  && <BrokerTab/>}
      {tab === "price"   && <PriceTab/>}
      {tab === "history" && <HistoryTab/>}
    </div>
  );
};

const AnomaliesView = () => (
  <div className="page">
    <div className="page-head">
      <div>
        <div className="eyebrow">AI insights</div>
        <div className="h1">Watchlist broker anomalies</div>
        <div className="subtitle">Comparing today's activity against 22-day historical baseline. Flagged when broker net volume is unusually high (z-score ≥ 1.5) or the Isolation Forest model marks it as anomalous.</div>
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

    <Card title="Flagged brokers · today" subtitle="Z-score outliers — Isolation Forest concurrence">
      <div style={{ overflow:"auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Broker</th>
              <th className="num right">Signal [today] (M)</th>
              <th className="num right">Baseline 22d (M)</th>
              <th className="num right">Z-score</th>
              <th className="num right">IF score</th>
              <th>Direction</th>
            </tr>
          </thead>
          <tbody>
            {D.ANOMALIES.map(a => (
              <tr key={a.code}>
                <td><span className="ticker-cell">{a.code}</span> <span className="muted2">— {a.name}</span></td>
                <td className="right num" style={{ color: a.signal>0 ? "var(--green)" : "var(--red)" }}>{a.signal>0?"+":""}{a.signal.toFixed(2)}</td>
                <td className="right num" style={{ color: a.baseline>0 ? "var(--green)" : "var(--red)" }}>{a.baseline>0?"+":""}{a.baseline.toFixed(2)}</td>
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

    <Card title="Isolation Forest — all watchlist brokers" subtitle="IF score ≥ 50 moderate · ≥ 70 strong"
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
