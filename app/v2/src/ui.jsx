// Shared UI primitives — Card, Badge, Sparkline, score widgets, broker chips, etc.

const colorForSub = (v) => {
  if (v >= 70) return "var(--green)";
  if (v >= 50) return "var(--accent)";
  if (v >= 35) return "var(--amber)";
  return "var(--red)";
};

const Card = ({ title, subtitle, actions, children }) => (
  <div className="card">
    {(title || actions) && (
      <div className="card-head">
        <div>
          {title    && <div className="h2">{title}</div>}
          {subtitle && <div className="subtitle">{subtitle}</div>}
        </div>
        {actions && <div className="card-actions">{actions}</div>}
      </div>
    )}
    {children}
  </div>
);

const Badge = ({ label }) => (
  <span className={`badge badge-${label}`}><span className="dot"/>{label.replace("_"," ")}</span>
);

const TrendArrow = ({ v = 0 }) => {
  if (v > 0)  return <span style={{ color:"var(--green)", fontSize:10, fontFamily:"var(--mono)" }}>▲ {v}</span>;
  if (v < 0)  return <span style={{ color:"var(--red)",   fontSize:10, fontFamily:"var(--mono)" }}>▼ {Math.abs(v)}</span>;
  return <span style={{ color:"var(--text-4)", fontSize:10 }}>⬬</span>;
};

// Bars removed — showing only the colored numeric value, easier to read in a dense table
const ScoreMini = ({ v }) => (
  <span style={{ fontFamily:"var(--mono)", fontWeight:600, color: colorForSub(v), fontVariantNumeric:"tabular-nums" }}>
    {v.toFixed(1)}
  </span>
);

const SparkBar = ({ v, color }) => (
  <span style={{ fontFamily:"var(--mono)", color: color || "var(--accent)", fontVariantNumeric:"tabular-nums" }}>
    {v.toFixed(1)}
  </span>
);

const AnomalyTag = ({ v }) => {
  const cls = v >= 70 ? "high" : v >= 50 ? "mid" : "low";
  const label = v >= 70 ? "High" : v >= 50 ? "Mod" : "Low";
  return <span className={`tag-anomaly ${cls}`}>{label} {v}</span>;
};

const XLXC = ({ v }) => {
  const map = {
    "net-buy":  { color:"var(--green)",  label:"Net buy",  icon:"▲" },
    "net-sell": { color:"var(--red)",    label:"Net sell", icon:"▼" },
    "balance":  { color:"var(--text-3)", label:"Balanced", icon:"⬬" },
    "neutral":  { color:"var(--text-3)", label:"Flat",     icon:"⬬" },
  };
  const m = map[v] || map.balance;
  return (
    <span className={`xlxc-pill ${v}`} style={{ color: m.color }}>
      {m.icon} {m.label}
    </span>
  );
};

const Sparkline = ({ data, w = 70, h = 22, color = "var(--accent)" }) => {
  if (!data || !data.length) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const step = w / (data.length - 1);
  const pts = data.map((v,i) => `${i*step},${(h - ((v-min)/range)*h).toFixed(1)}`).join(" ");
  const id = `sl-${Math.random().toString(36).slice(2, 7)}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#${id})`}/>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round"/>
    </svg>
  );
};

const ScoreWheel = ({ value, label = "score", sub, size = 132 }) => {
  const r = (size/2) - 10;
  const c = size/2;
  const circ = 2 * Math.PI * r;
  const dash = circ * Math.min(1, value/100);
  const col = colorForSub(value);
  return (
    <svg width={size} height={size} className="score-wheel">
      <defs>
        <linearGradient id={`g-wheel-${label}`} x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%"  stopColor="var(--accent)"/>
          <stop offset="100%" stopColor={col}/>
        </linearGradient>
      </defs>
      <circle cx={c} cy={c} r={r} stroke="oklch(1 0 0 / 0.06)" strokeWidth="6" fill="none"/>
      <circle cx={c} cy={c} r={r}
        stroke={`url(#g-wheel-${label})`} strokeWidth="6" fill="none" strokeLinecap="round"
        strokeDasharray={`${dash} ${circ}`} transform={`rotate(-90 ${c} ${c})`}/>
      <text x={c} y={c-2} textAnchor="middle" fill="var(--text)"
        style={{ fontFamily:"var(--mono)", fontSize:24, fontWeight:600, fontVariantNumeric:"tabular-nums" }}>
        {Math.round(value)}
      </text>
      <text x={c} y={c+18} textAnchor="middle" fill="var(--text-3)"
        style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase" }}>
        {sub || "/ 100"}
      </text>
    </svg>
  );
};

const DistBar = ({ sellPct, buyPct }) => (
  <div className="distbar-wrap">
    <div className="distbar-head">
      <span className="sell">▼ SELL {sellPct}%</span>
      <span className="ctr">institutional net vs retail net</span>
      <span className="buy">BUY {buyPct}% ▲</span>
    </div>
    <div className="distbar">
      <div className="seg sell" style={{ width: `${sellPct}%` }}/>
      <div className="seg buy"  style={{ width: `${buyPct}%`  }}/>
      <div className="midmark" style={{ left: "50%" }}/>
    </div>
    <div className="distbar-foot">⬬ equilibrium</div>
  </div>
);

Object.assign(window, {
  colorForSub, Card, Badge, TrendArrow, ScoreMini, SparkBar, AnomalyTag, XLXC,
  Sparkline, ScoreWheel, DistBar
});
