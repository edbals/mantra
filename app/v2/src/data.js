// Static demo data for the IDX screener prototype.
(function () {
  const seed = (s) => { let x = s; return () => { x = (x*9301+49297)%233280; return x/233280; }; };
  const r = seed(7);

  const RAW = [
    ["MDIA","Intermedia Capital",      "INVEST",     78.4, true,  82, 71, 73, "net-buy",  410,  18.3,  +3 ],
    ["GOTO","GoTo Gojek Tokopedia",    "INVEST",     74.1, true,  80, 68, 84, "net-buy",   62,  92.6,  +5 ],
    ["MAPI","Mitra Adiperkasa",        "INVEST",     71.6, false, 76, 70, 64, "net-buy", 1490,  24.1,  +2 ],
    ["MEDS","Hutomo Medika",           "WATCH_EXEC", 68.9, true,  72, 66, 78, "net-buy",  366,   8.4,  +6 ],
    ["BBRI","Bank Rakyat Indonesia",   "WATCH_EXEC", 66.3, false, 64, 71, 31, "net-sell",4480, 612.3,  -1 ],
    ["BBCA","Bank Central Asia",       "WATCH_EXEC", 65.4, false, 62, 70, 26, "balance", 9425, 488.0,   0 ],
    ["TLKM","Telkom Indonesia",        "WATCH",      62.1, false, 58, 64, 18, "balance", 2820, 281.4,  -2 ],
    ["ASII","Astra International",     "WATCH",      60.8, false, 60, 62, 22, "net-sell",4670, 197.5,  -1 ],
    ["UNVR","Unilever Indonesia",      "WATCH",      58.4, false, 54, 56, 41, "net-sell",2340,  88.2,  +1 ],
    ["BMRI","Bank Mandiri",            "WATCH",      57.9, false, 56, 59, 19, "balance", 6175, 322.0,   0 ],
    ["ICBP","Indofood CBP",            "WATCH",      56.2, false, 52, 60, 24, "balance",11000, 142.6,  +1 ],
    ["ADRO","Adaro Energy",            "WATCH",      54.7, true,  60, 46, 48, "net-buy", 2710,  74.3,  +4 ],
    ["INDF","Indofood Sukses Makmur",  "OBSERVE",    49.1, false, 46, 50, 12, "balance", 6650,  68.1,   0 ],
    ["KLBF","Kalbe Farma",             "OBSERVE",    47.6, false, 42, 52, 16, "balance", 1620,  56.0,  -1 ],
    ["EXCL","XL Axiata",               "OBSERVE",    44.8, false, 40, 48, 28, "net-sell",2380,  39.7,  -2 ],
    ["ANTM","Aneka Tambang",           "OBSERVE",    42.5, false, 38, 46, 33, "net-sell",1745,  61.2,  -3 ],
    ["BRPT","Barito Pacific",          "OBSERVE",    41.0, false, 44, 38, 21, "balance",  995,  44.5,  +1 ],
    ["JSMR","Jasa Marga",              "OBSERVE",    39.2, false, 36, 42, 15, "balance", 4940,  27.4,   0 ],
    ["PGAS","Perusahaan Gas Negara",   "OBSERVE",    36.4, false, 34, 39, 19, "balance", 1565,  30.1,  -1 ],
    ["WIKA","Wijaya Karya",            "OBSERVE",    32.7, false, 30, 36, 24, "net-sell",  256,  18.6,  -2 ],
  ];

  const RANKINGS = RAW.map(([ticker,name,action,score,breakout,bf,fp,anomaly,xlxc,close,advB,trend], i) => ({
    rank: i+1, ticker, name, action, score, breakout,
    brokerFlow: bf, floatPressure: fp, anomaly,
    xlxc, close, advB, trend
  }));

  const SUBSCORES = {
    bf:  { label: "Broker flow",      val: 78, weight: 0.40 },
    fp:  { label: "Float pressure",   val: 71, weight: 0.30 },
    liq: { label: "Liquidity",        val: 64, weight: 0.20 },
    str: { label: "Structure",        val: 52, weight: 0.10 },
  };

  const FLOW_SIGNALS = [
    { label:"Institutional absorption", value:"Detected", desc:"Top 5 institutional buyers absorbing >60% of XL/XC retail supply over last 3 sessions.", tone:"green" },
    { label:"XL / XC divergence",       value:"+2.4σ",     desc:"Retail brokers selling against rising price — classic bullish divergence signature.", tone:"green" },
    { label:"Concentration ratio",      value:"0.71",      desc:"Top-10 brokers control 71% of net flow. Above 22-day baseline of 0.58.", tone:"amber" },
    { label:"Foreign net flow",         value:"−4.1B IDR", desc:"Foreign brokers (KZ, CS, DB) modest sellers; offset by domestic institutions.", tone:"red"   },
  ];

  const TOP_BUYERS = [
    { code:"MG", name:"Semesta Indovest",       buy: 8.42, sell: 1.10 },
    { code:"RG", name:"Mandiri Sekuritas",      buy: 6.81, sell: 0.94 },
    { code:"CC", name:"Mandiri Sekuritas (CC)", buy: 5.27, sell: 1.32 },
    { code:"NI", name:"BNI Sekuritas",          buy: 4.12, sell: 0.61 },
    { code:"PD", name:"Indo Premier",           buy: 3.55, sell: 0.42 },
    { code:"BR", name:"Trimegah Sekuritas",     buy: 2.18, sell: 0.71 },
  ];

  const TOP_SELLERS = [
    { code:"YP", name:"Mirae Asset Sekuritas",  buy: 0.94, sell: 9.21 },
    { code:"XL", name:"Mahakarya Artha",        buy: 1.64, sell: 7.83 },
    { code:"XC", name:"Bahana Sekuritas (XC)",  buy: 0.71, sell: 6.40 },
    { code:"DX", name:"Bahana Sekuritas",       buy: 1.02, sell: 4.72 },
    { code:"KZ", name:"CLSA Sekuritas",         buy: 0.30, sell: 3.81 },
    { code:"AK", name:"UBS Sekuritas",          buy: 0.85, sell: 2.92 },
  ];

  const BROKER_NET = [
    { code:"MG", net: +7.32 },{ code:"RG", net: +5.87 },{ code:"CC", net: +3.95 },
    { code:"NI", net: +3.51 },{ code:"PD", net: +3.13 },{ code:"BR", net: +1.47 },
    { code:"OD", net: +1.12 },{ code:"DR", net: +0.74 },{ code:"AI", net: +0.21 },
    { code:"BK", net: -0.40 },{ code:"AK", net: -2.07 },{ code:"KZ", net: -3.51 },
    { code:"DX", net: -3.70 },{ code:"XC", net: -5.69 },{ code:"XL", net: -6.19 },
    { code:"YP", net: -8.27 },
  ];

  const PRICE_SERIES = (() => {
    const out = []; let close = 380;
    for (let i = 0; i < 30; i++) {
      const drift = (i / 30) * 35;
      const noise = (r() - 0.5) * 14;
      close = Math.max(320, 380 + drift + noise);
      const vol = 8e6 + r() * 18e6 + (i > 22 ? 15e6 * r() : 0);
      const day = new Date(2026, 3, 9);
      day.setDate(day.getDate() + i);
      out.push({ date: day.toISOString().slice(5,10), close: Math.round(close), volume: Math.round(vol) });
    }
    return out;
  })();

  const SCORE_HISTORY = (() => {
    const out = []; let s = 52, b = 60;
    for (let i = 0; i < 12; i++) {
      s += (r() - 0.4) * 6;
      b += (r() - 0.45) * 7;
      s = Math.max(40, Math.min(82, s));
      b = Math.max(35, Math.min(90, b));
      const day = new Date(2026, 3, 24);
      day.setDate(day.getDate() + i);
      const action = s > 70 ? "INVEST" : s > 60 ? "WATCH_EXEC" : s > 50 ? "WATCH" : "OBSERVE";
      out.push({ date: day.toISOString().slice(0,10), action, invest: +s.toFixed(1), bf: +b.toFixed(1) });
    }
    return out;
  })();

  const ANOMALIES = [
    { code:"MG", name:"Semesta Indovest",      signal: +12.4, baseline:+2.1, z:+4.8, ifScore:84, dir:"buy"  },
    { code:"YP", name:"Mirae Asset Sekuritas", signal: -10.7, baseline:-1.4, z:-4.1, ifScore:79, dir:"sell" },
    { code:"XL", name:"Mahakarya Artha",       signal:  -8.9, baseline:-2.0, z:-3.2, ifScore:72, dir:"sell" },
    { code:"RG", name:"Mandiri Sekuritas",     signal:  +7.6, baseline:+1.8, z:+2.7, ifScore:68, dir:"buy"  },
    { code:"XC", name:"Bahana Sekuritas (XC)", signal:  -6.4, baseline:-1.2, z:-2.4, ifScore:61, dir:"sell" },
    { code:"CC", name:"Mandiri Sekuritas (CC)",signal:  +4.7, baseline:+1.5, z:+1.9, ifScore:54, dir:"buy"  },
    { code:"KZ", name:"CLSA Sekuritas",        signal:  -3.8, baseline:-0.9, z:-1.7, ifScore:51, dir:"sell" },
  ];

  const ISOLATION_FOREST = [
    { code:"MG", name:"Semesta Indovest",       score: 84, dir:"buy"  },
    { code:"YP", name:"Mirae Asset Sekuritas",  score: 79, dir:"sell" },
    { code:"XL", name:"Mahakarya Artha",        score: 72, dir:"sell" },
    { code:"RG", name:"Mandiri Sekuritas",      score: 68, dir:"buy"  },
    { code:"XC", name:"Bahana Sekuritas",       score: 61, dir:"sell" },
    { code:"CC", name:"Mandiri CC",             score: 54, dir:"buy"  },
    { code:"KZ", name:"CLSA Sekuritas",         score: 51, dir:"sell" },
    { code:"NI", name:"BNI Sekuritas",          score: 47, dir:"buy"  },
    { code:"DX", name:"Bahana Sekuritas",       score: 44, dir:"sell" },
    { code:"PD", name:"Indo Premier",           score: 41, dir:"buy"  },
    { code:"AK", name:"UBS Sekuritas",          score: 38, dir:"sell" },
    { code:"BR", name:"Trimegah Sekuritas",     score: 33, dir:"buy"  },
  ];

  window.IDX_DATA = {
    RANKINGS, SUBSCORES, FLOW_SIGNALS,
    TOP_BUYERS, TOP_SELLERS, BROKER_NET,
    PRICE_SERIES, SCORE_HISTORY, ANOMALIES, ISOLATION_FOREST
  };
})();
