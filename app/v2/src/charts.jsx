// Custom-rendered SVG charts.
const { useState: useStateC, useMemo: useMemoC } = React;

const NetVolumeBars = ({ data, height=460 }) => {
  const sorted = [...data].sort((a,b)=>b.net - a.net);
  const max = Math.max(...sorted.map(d => Math.abs(d.net)));
  const padded = Math.ceil(max / 4) * 4 || 4;
  const W = 920, H = height;
  const padL = 56, padR = 22, padT = 14, padB = 28;
  const innerW = W - padL - padR;
  const rowH = (H - padT - padB) / sorted.length;
  const x0 = padL + innerW/2;
  const xScale = (v) => x0 + (v / padded) * (innerW/2);

  const ticks = [];
  for (let v = -padded; v <= padded; v += padded/5) ticks.push(+v.toFixed(1));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display:"block" }}>
      <defs>
        <linearGradient id="bar-buy" x1="0" x2="1">
          <stop offset="0" stopColor="oklch(0.7 0.18 142 / 0.4)"/>
          <stop offset="1" stopColor="var(--green)"/>
        </linearGradient>
        <linearGradient id="bar-sell" x1="1" x2="0">
          <stop offset="0" stopColor="oklch(0.6 0.21 28 / 0.4)"/>
          <stop offset="1" stopColor="var(--red)"/>
        </linearGradient>
      </defs>

      {ticks.map((t,i) => (
        <line key={i} x1={xScale(t)} x2={xScale(t)} y1={padT} y2={H-padB}
          className="grid-line" strokeDasharray={t===0 ? "" : "3 4"}
          stroke={t===0 ? "var(--line-2)" : ""}/>
      ))}
      {ticks.map((t,i) => (
        <text key={i} x={xScale(t)} y={H-padB+14} textAnchor="middle" className="axis-tick">{t}</text>
      ))}
      {sorted.map((d,i) => {
        const y = padT + i * rowH;
        const isBuy = d.net >= 0;
        const w = Math.abs(xScale(d.net) - x0);
        const x = isBuy ? x0 : x0 - w;
        return (
          <g key={d.code}>
            <text x={padL - 10} y={y + rowH/2 + 3} textAnchor="end"
              fill="var(--text-2)" style={{ fontFamily:"var(--mono)", fontSize:11, fontWeight:600 }}>
              {d.code}
            </text>
            <rect x={x} y={y + 3} width={w} height={rowH - 6} rx="2"
              fill={isBuy ? "url(#bar-buy)" : "url(#bar-sell)"}/>
            <text x={isBuy ? x + w + 6 : x - 6} y={y + rowH/2 + 3}
              textAnchor={isBuy ? "start" : "end"}
              fill={isBuy ? "var(--green)" : "var(--red)"}
              style={{ fontFamily:"var(--mono)", fontSize:11, fontWeight:600 }}>
              {d.net > 0 ? "+" : ""}{d.net.toFixed(1)}
            </text>
          </g>
        );
      })}
      <text x={W/2} y={H-4} textAnchor="middle" fill="var(--text-3)"
        style={{ fontSize:11, letterSpacing:"0.08em", textTransform:"uppercase" }}>
        net volume (M lots)
      </text>
    </svg>
  );
};

const ScoreHistoryChart = ({ data, height=300 }) => {
  const W = 920, H = height;
  const padL = 38, padR = 18, padT = 18, padB = 36;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const max = 100, min = 0;
  const xs = data.map((_,i) => padL + (i/(data.length-1))*innerW);
  const ys = (v) => padT + (1 - (v - min)/(max - min)) * innerH;

  const linePath = (key) => data.map((d,i)=>(i===0?"M":"L") + xs[i] + " " + ys(d[key])).join(" ");
  const areaPath = (key) => linePath(key) + ` L ${xs[xs.length-1]} ${padT+innerH} L ${xs[0]} ${padT+innerH} Z`;

  const yTicks = [0, 20, 40, 60, 80, 100];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
      <defs>
        <linearGradient id="hist-area-invest" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--accent)" stopOpacity="0.28"/>
          <stop offset="1" stopColor="var(--accent)" stopOpacity="0"/>
        </linearGradient>
        <linearGradient id="hist-area-bf" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--orange)" stopOpacity="0.20"/>
          <stop offset="1" stopColor="var(--orange)" stopOpacity="0"/>
        </linearGradient>
      </defs>

      {yTicks.map((t,i)=>(
        <g key={t}>
          <line x1={padL} x2={W-padR} y1={ys(t)} y2={ys(t)} className="grid-line"/>
          <text x={padL-8} y={ys(t)+3} textAnchor="end" className="axis-tick">{t}</text>
        </g>
      ))}

      <path d={areaPath("invest")} fill="url(#hist-area-invest)"/>
      <path d={linePath("invest")} stroke="var(--accent)" strokeWidth="2" fill="none" strokeLinejoin="round"/>

      <path d={areaPath("bf")} fill="url(#hist-area-bf)"/>
      <path d={linePath("bf")} stroke="var(--orange)" strokeWidth="2" fill="none" strokeLinejoin="round"/>

      {[
        { v: data[data.length-1].invest, color: "var(--accent)" },
        { v: data[data.length-1].bf,     color: "var(--orange)" }
      ].map((p,i)=>(
        <g key={i}>
          <circle cx={xs[xs.length-1]} cy={ys(p.v)} r="6" fill={p.color} fillOpacity="0.18"/>
          <circle cx={xs[xs.length-1]} cy={ys(p.v)} r="3" fill={p.color}/>
        </g>
      ))}

      {data.map((d,i)=>(
        <text key={i} x={xs[i]} y={H-padB+14} textAnchor="middle" className="axis-tick">{d.date.slice(5)}</text>
      ))}
      <text x={padL} y={12} fill="var(--text-3)" style={{ fontSize:10.5, letterSpacing:"0.1em", textTransform:"uppercase" }}>Score · 0–100</text>
    </svg>
  );
};

const PriceVolumeChart = ({ data, height=380 }) => {
  const W = 920, H = height;
  const padL = 50, padR = 18, padT = 14, padB = 36;
  const priceH = (H - padT - padB) * 0.66;
  const volH   = (H - padT - padB) * 0.30;
  const gap = (H - padT - padB) * 0.04;

  const minP = Math.min(...data.map(d=>d.close));
  const maxP = Math.max(...data.map(d=>d.close));
  const rangeP = maxP - minP || 1;
  const maxV = Math.max(...data.map(d=>d.volume));
  const innerW = W - padL - padR;
  const xs = data.map((_,i) => padL + (i/(data.length-1))*innerW);
  const yP = (v) => padT + priceH - ((v - minP)/rangeP) * priceH;

  const linePath = data.map((d,i)=>(i===0?"M":"L") + xs[i] + " " + yP(d.close)).join(" ");
  const areaPath = linePath + ` L ${xs[xs.length-1]} ${padT+priceH} L ${xs[0]} ${padT+priceH} Z`;

  const yTicksP = 5;
  const priceTicks = [];
  for (let i=0;i<=yTicksP;i++) priceTicks.push(+(minP + (rangeP/yTicksP)*i).toFixed(0));

  const labels = data.filter((_,i)=>i%4===0 || i===data.length-1);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
      <defs>
        <linearGradient id="price-area" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--accent)" stopOpacity="0.32"/>
          <stop offset="1" stopColor="var(--accent)" stopOpacity="0"/>
        </linearGradient>
      </defs>
      {priceTicks.map((t,i)=>(
        <g key={i}>
          <line x1={padL} x2={W-padR} y1={yP(t)} y2={yP(t)} className="grid-line"/>
          <text x={padL-8} y={yP(t)+3} textAnchor="end" className="axis-tick">{t}</text>
        </g>
      ))}
      <path d={areaPath} fill="url(#price-area)"/>
      <path d={linePath} stroke="var(--accent)" strokeWidth="2" fill="none" strokeLinejoin="round"/>
      <circle cx={xs[xs.length-1]} cy={yP(data[data.length-1].close)} r="6" fill="var(--accent)" fillOpacity="0.16"/>
      <circle cx={xs[xs.length-1]} cy={yP(data[data.length-1].close)} r="3" fill="var(--accent)"/>

      {data.map((d,i) => {
        const x = xs[i] - 6;
        const h = (d.volume / maxV) * volH;
        const y = padT + priceH + gap + (volH - h);
        const prev = i > 0 ? data[i-1].close : d.close;
        const up = d.close >= prev;
        return <rect key={i} x={x} y={y} width="12" height={h} rx="1.5"
          fill={up ? "oklch(0.65 0.18 142 / 0.55)" : "oklch(0.6 0.21 28 / 0.55)"}/>;
      })}
      {labels.map((d) => {
        const i = data.indexOf(d);
        return <text key={i} x={xs[i]} y={H-padB+18} textAnchor="middle" className="axis-tick">{d.date}</text>;
      })}
      <text x={padL} y={11} fill="var(--text-3)" style={{ fontSize:10.5, letterSpacing:"0.1em", textTransform:"uppercase" }}>Close · IDR</text>
      <text x={padL} y={padT+priceH+gap+10} fill="var(--text-3)" style={{ fontSize:10.5, letterSpacing:"0.1em", textTransform:"uppercase" }}>Volume</text>
    </svg>
  );
};

const IsolationForest = ({ data, height=380 }) => {
  const sorted = [...data].sort((a,b)=>a.score - b.score);
  const W = 920, H = height;
  const padL = 130, padR = 30, padT = 14, padB = 32;
  const innerW = W - padL - padR;
  const rowH = (H - padT - padB) / sorted.length;
  const xScale = (v) => padL + (v/100) * innerW;
  const moderate = xScale(50), strong = xScale(70);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
      <defs>
        <linearGradient id="if-buy" x1="0" x2="1">
          <stop offset="0" stopColor="oklch(0.65 0.18 142 / 0.4)"/>
          <stop offset="1" stopColor="var(--green)"/>
        </linearGradient>
        <linearGradient id="if-sell" x1="0" x2="1">
          <stop offset="0" stopColor="oklch(0.6 0.21 28 / 0.4)"/>
          <stop offset="1" stopColor="var(--red)"/>
        </linearGradient>
      </defs>
      {[0,10,20,30,40,50,60,70,80,90,100].map(t => (
        <g key={t}>
          <line x1={xScale(t)} x2={xScale(t)} y1={padT} y2={H-padB} className="grid-line"/>
          <text x={xScale(t)} y={H-padB+15} textAnchor="middle" className="axis-tick">{t}</text>
        </g>
      ))}
      <line x1={moderate} x2={moderate} y1={padT} y2={H-padB} stroke="var(--orange)" strokeWidth="1" strokeDasharray="4 4"/>
      <line x1={strong}   x2={strong}   y1={padT} y2={H-padB} stroke="var(--red)"    strokeWidth="1" strokeDasharray="4 4"/>
      <text x={moderate} y={padT+4} textAnchor="middle" fill="var(--orange)" style={{ fontSize:10, letterSpacing:"0.08em" }}>moderate</text>
      <text x={strong}   y={padT+4} textAnchor="middle" fill="var(--red)"    style={{ fontSize:10, letterSpacing:"0.08em" }}>strong</text>

      {sorted.map((d,i) => {
        const y = padT + i * rowH;
        const w = xScale(d.score) - padL;
        const isBuy = d.dir === "buy";
        return (
          <g key={d.code}>
            <text x={padL - 8} y={y + rowH/2 + 3} textAnchor="end" fill="var(--text-2)"
              style={{ fontFamily:"var(--mono)", fontSize:11 }}>
              {d.code} — {d.name.split(" ").slice(0,2).join(" ")}
            </text>
            <rect x={padL} y={y+3} width={w} height={rowH-6} rx="2"
              fill={isBuy ? "url(#if-buy)" : "url(#if-sell)"}/>
            <text x={padL + w + 6} y={y + rowH/2 + 3} fill={isBuy ? "var(--green)" : "var(--red)"}
              style={{ fontFamily:"var(--mono)", fontSize:11, fontWeight:600 }}>
              {d.score}
            </text>
          </g>
        );
      })}
      <text x={padL + innerW/2} y={H-4} textAnchor="middle" fill="var(--text-3)"
        style={{ fontSize:11, letterSpacing:"0.08em", textTransform:"uppercase" }}>
        IF anomaly score (0–100)
      </text>
    </svg>
  );
};

Object.assign(window, { NetVolumeBars, ScoreHistoryChart, PriceVolumeChart, IsolationForest });
