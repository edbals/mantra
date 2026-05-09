// Icon set — all stroke-only line icons with consistent metrics.
const Icon = ({ children, w = 16, s = 1.6, vb = 24 }) => (
  <svg width={w} height={w} viewBox={`0 0 ${vb} ${vb}`} fill="none"
       stroke="currentColor" strokeWidth={s} strokeLinecap="round" strokeLinejoin="round">
    {children}
  </svg>
);

const IconDashboard = (p) => <Icon {...p}><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></Icon>;
const IconScreener  = (p) => <Icon {...p}><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/><path d="M8 11h6M11 8v6"/></Icon>;
const IconAI        = (p) => <Icon {...p}><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/><circle cx="12" cy="12" r="3"/></Icon>;
const IconAnalytics = (p) => <Icon {...p}><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/></Icon>;
const IconBroker    = (p) => <Icon {...p}><rect x="3" y="9" width="18" height="11" rx="1"/><path d="M3 9l9-6 9 6"/><path d="M9 20v-6h6v6"/></Icon>;
const IconSettings  = (p) => <Icon {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></Icon>;

const IconCheck     = (p) => <Icon {...p}><path d="M4 12l5 5L20 6"/></Icon>;
const IconBookmark  = (p) => <Icon {...p}><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></Icon>;
const IconChartBar  = (p) => <Icon {...p}><path d="M3 21V8M9 21V3M15 21v-9M21 21v-5"/></Icon>;
const IconAnomaly   = (p) => <Icon {...p}><path d="M12 2 2 22h20L12 2z"/><path d="M12 9v5M12 17v.01"/></Icon>;
const IconCalendar  = (p) => <Icon {...p}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></Icon>;
const IconRefresh   = (p) => <Icon {...p}><path d="M3 12a9 9 0 0 1 15.5-6.4L21 8M21 4v4h-4"/><path d="M21 12a9 9 0 0 1-15.5 6.4L3 16M3 20v-4h4"/></Icon>;
const IconArrowUp   = (p) => <Icon {...p}><path d="M12 19V5M5 12l7-7 7 7"/></Icon>;
const IconArrowDown = (p) => <Icon {...p}><path d="M12 5v14M19 12l-7 7-7-7"/></Icon>;
const IconArrowFlat = (p) => <Icon {...p}><path d="M5 12h14"/></Icon>;
const IconBolt      = (p) => <Icon {...p}><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/></Icon>;
const IconHistory   = (p) => <Icon {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/></Icon>;
const IconExpand    = (p) => <Icon {...p}><path d="M3 9V3h6M21 9V3h-6M3 15v6h6M21 15v6h-6"/></Icon>;
const IconSearch    = (p) => <Icon {...p}><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></Icon>;
const IconBell      = (p) => <Icon {...p}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9z"/><path d="M10 21a2 2 0 0 0 4 0"/></Icon>;
const IconDownload  = (p) => <Icon {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></Icon>;

// Mantra pixel-art M logo. White rounded squares on transparent background.
// 5 columns × 5 rows — legs cropped tight so the M reads square-ish.
const M_PATTERN = [
  [1,0,0,0,1],
  [1,1,0,1,1],
  [1,0,1,0,1],
  [1,0,0,0,1],
  [1,0,0,0,1],
];
const PixelM = ({ size = 26, color = "#fff" }) => {
  const cols = M_PATTERN[0].length;
  const rows = M_PATTERN.length;
  const cell = size / cols;
  const dotSize = cell * 0.78;
  const radius = dotSize * 0.22;
  const dots = [];
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      if (!M_PATTERN[y][x]) continue;
      dots.push(
        <rect
          key={`${x}-${y}`}
          x={x * cell + (cell - dotSize) / 2}
          y={y * cell + (cell - dotSize) / 2}
          width={dotSize}
          height={dotSize}
          rx={radius}
          ry={radius}
          fill={color}
        />
      );
    }
  }
  return (
    <svg width={size} height={(size / cols) * rows} viewBox={`0 0 ${size} ${(size/cols)*rows}`} style={{ display:"block" }}>
      {dots}
    </svg>
  );
};

Object.assign(window, {
  Icon, IconDashboard, IconScreener, IconAI, IconAnalytics, IconBroker, IconSettings,
  IconCheck, IconBookmark, IconChartBar, IconAnomaly, IconCalendar, IconRefresh,
  IconArrowUp, IconArrowDown, IconArrowFlat, IconBolt, IconHistory, IconExpand,
  IconSearch, IconBell, IconDownload, PixelM,
});
