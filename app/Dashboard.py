"""
Mantra Dashboard — MyMantra
Run: streamlit run app/dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import altair as alt
import pandas as pd
import streamlit as st

from app.cache import (
    cached_available_dates,
    cached_broker_history,
    cached_broker_master,
    cached_broker_names,
    cached_broker_summary,
    cached_scores_for_date,
    cached_ticker_flow,
    cached_ticker_history,
    ensure_today_scored,
    latest_idx_trading_date,
)

CONFIG_PATH = str(Path(__file__).parent.parent / "config.json")

# ── Design tokens ─────────────────────────────────────────────────────────────
# Decision-label pill palette: (background, text). Same hues across modes; the
# 10-12% opacity background reads correctly on both light and dark surfaces.
ACTION_PILL = {
    "INVEST":     ("#D1FAE5", "#065F46"),
    "WATCH_EXEC": ("#FEF9C3", "#854D0E"),
    "WATCH":      ("#FEF3C7", "#92400E"),
    "OBSERVE":    ("#FFEDD5", "#9A3412"),
    "AVOID":      ("#FEE2E2", "#991B1B"),
    "ILLIQUID":   ("#F3F4F6", "#374151"),
}

# Single accent per action used for chart colors / outlines (mode-agnostic).
ACTION_COLORS = {k: v[1] for k, v in ACTION_PILL.items()}

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mantra",
    page_icon=":material/candlestick_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Mode state ────────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "onboarding_done" not in st.session_state:
    st.session_state.onboarding_done = False

_DARK = st.session_state.dark_mode

# ── Global theme + typography ─────────────────────────────────────────────────
# CSS variables driven off the toggle. Colors are kept on `:root` so Altair-free
# inline styles can also reference them (we expose them via Python below too).
_LIGHT_VARS = {
    "page": "#F2EDE6", "card": "#FFFFFF",
    "text": "#0C0B09", "muted": "#8A8276", "border": "#E8E2DA",
    "track": "#F5F0EB", "row_hover": "#FAF7F3",
}
_DARK_VARS = {
    "page": "#0C0B09", "card": "#161412",
    "text": "#F7F3EE", "muted": "#9A9189", "border": "#2A2723",
    "track": "#1F1C19", "row_hover": "#1A1815",
}
T = _DARK_VARS if _DARK else _LIGHT_VARS

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  :root {{
    --m-page: {T['page']};
    --m-card: {T['card']};
    --m-text: {T['text']};
    --m-muted: {T['muted']};
    --m-border: {T['border']};
    --m-track: {T['track']};
    --m-row-hover: {T['row_hover']};
  }}

  html, body, [class*="css"], [data-testid="stAppViewContainer"] *,
  [data-testid="stSidebar"] * {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }}

  [data-testid="stAppViewContainer"] {{
    background-color: {T['page']} !important;
  }}
  [data-testid="stSidebar"] {{
    background-color: {T['card']} !important;
    border-right: 1px solid {T['border']} !important;
  }}
  [data-testid="stSidebar"] *,
  [data-testid="stAppViewContainer"] p,
  [data-testid="stAppViewContainer"] span,
  [data-testid="stAppViewContainer"] li,
  [data-testid="stAppViewContainer"] label {{
    color: {T['text']};
  }}
  h1, h2, h3, h4 {{
    color: {T['text']} !important;
    letter-spacing: -0.025em;
    font-weight: 600;
  }}
  h1 {{ letter-spacing: -0.03em; font-weight: 700; }}

  /* Hide Streamlit chrome */
  #MainMenu, footer, header {{ visibility: hidden; }}

  /* Caption styling — used for Level-1 labels */
  [data-testid="stCaptionContainer"], .m-eyebrow {{
    color: {T['muted']} !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 500;
  }}

  /* Ramp-style stat */
  .m-stat {{ padding: 16px 0 8px 0; }}
  .m-stat .label {{
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em;
    color: {T['muted']}; margin-bottom: 6px; font-weight: 500;
  }}
  .m-stat .num {{
    font-size: 56px; font-weight: 700; color: {T['text']};
    line-height: 1; letter-spacing: -0.04em; margin: 0;
    font-variant-numeric: tabular-nums;
  }}
  .m-stat .num.small {{ font-size: 32px; }}
  .m-stat .sub {{ font-size: 13px; color: {T['muted']}; margin-top: 6px; }}

  /* Decision label pills */
  .m-pill {{
    display: inline-block; padding: 3px 10px; border-radius: 99px;
    font-size: 12px; font-weight: 500; letter-spacing: 0.01em;
    line-height: 1.4;
  }}

  /* Card shell */
  .m-card {{
    background-color: {T['card']};
    border: 1px solid {T['border']};
    border-radius: 12px;
    padding: 24px 28px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 16px;
  }}

  /* Sub-score row (bar + label) */
  .m-sub-row {{ margin: 10px 0; }}
  .m-sub-label {{
    display: flex; justify-content: space-between; align-items: baseline;
    font-size: 13px; color: {T['text']}; margin-bottom: 4px;
  }}
  .m-sub-label .weight {{ color: {T['muted']}; font-size: 11px; margin-left: 6px; }}
  .m-sub-label b {{ font-variant-numeric: tabular-nums; font-weight: 600; }}
  .m-bar-track {{
    background: {T['track']}; border-radius: 99px; height: 6px; overflow: hidden;
  }}
  .m-bar-fill {{ height: 6px; border-radius: 99px; }}

  /* Concentration gauge */
  .m-gauge-wrap {{
    background: {T['track']}; border-radius: 99px; height: 10px;
    overflow: hidden; position: relative; margin: 10px 0 6px 0;
  }}
  .m-gauge-sell {{ position: absolute; left: 0;  top: 0; height: 100%; background: #DC2626; }}
  .m-gauge-buy  {{ position: absolute; right: 0; top: 0; height: 100%; background: #16A34A; }}

  /* Tables: lighter feel */
  div[data-testid="stDataFrame"] {{
    border-radius: 12px; overflow: hidden;
    border: 1px solid {T['border']};
  }}
  div[data-testid="stDataFrame"] thead tr th {{
    background-color: {T['card']} !important;
    color: {T['muted']} !important;
    text-transform: uppercase; font-size: 11px !important;
    letter-spacing: 0.05em; font-weight: 500 !important;
    border-bottom: 1px solid {T['border']} !important;
  }}

  /* Onboarding card */
  .m-onboard {{
    background-color: {T['card']}; border: 1px solid {T['border']};
    border-radius: 14px; padding: 32px 36px; margin: 16px 0 24px 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  }}
  .m-onboard h2 {{ font-size: 28px; margin: 0 0 12px 0; }}
  .m-onboard p {{ font-size: 15px; color: {T['text']}; line-height: 1.65; margin: 8px 0; }}

  /* Inputs */
  [data-baseweb="input"] input, .stSelectbox > div > div {{
    background-color: {T['card']} !important;
    border-color: {T['border']} !important;
  }}
</style>
""", unsafe_allow_html=True)


# ── Theme-aware Python tokens (used in inline HTML strings below) ─────────────
M_TEXT = T["text"]; M_MUTED = T["muted"]; M_CARD = T["card"]
M_BORDER = T["border"]; M_TRACK = T["track"]; M_PAGE = T["page"]
ALTAIR_GREEN = "#16A34A"; ALTAIR_RED = "#DC2626"
ALTAIR_NEUTRAL = "#9CA3AF"; ALTAIR_AMBER = "#F59E0B"


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def fmt(val, spec: str = ",.0f", fallback: str = "N/A") -> str:
    try:
        return format(float(val), spec)
    except (TypeError, ValueError):
        return fallback


def score_color(v: float) -> str:
    """Colour for a 0–100 score. Used for chart accents and sub-score bars."""
    if v >= 70:   return "#16A34A"   # green
    if v >= 50:   return "#F59E0B"   # amber
    if v >= 35:   return "#EA580C"   # orange
    return "#DC2626"                  # red


def action_badge_html(action: str) -> str:
    bg, fg = ACTION_PILL.get(action, ACTION_PILL["ILLIQUID"])
    return (
        f"<span class='m-pill' style='background:{bg};color:{fg}'>"
        f"{action.replace('_', ' ').title() if action != 'INVEST' and action != 'AVOID' else action}"
        f"</span>"
    )


def subscore_bar(label: str, weight: str, val: float) -> str:
    pct = min(max(val, 0), 100)
    c = score_color(pct)
    return f"""
    <div class="m-sub-row">
      <div class="m-sub-label">
        <span>{label}<span class="weight">{weight}</span></span>
        <b style="color:{c}">{val:.1f}</b>
      </div>
      <div class="m-bar-track">
        <div class="m-bar-fill" style="width:{pct}%;background:{c}"></div>
      </div>
    </div>"""


def concentration_gauge(buy_pct: float, subtitle: str = "buy vs sell concentration") -> str:
    sell_pct = 100 - buy_pct
    sell_c, buy_c, neutral = "#DC2626", "#16A34A", M_MUTED
    if buy_pct > 60:
        label = "Accumulation"
        label_c = buy_c
    elif buy_pct < 40:
        label = "Distribution"
        label_c = sell_c
    else:
        label = "Balanced"
        label_c = neutral
    return f"""
    <div style="margin:14px 0 4px 0">
      <div style="display:flex;justify-content:space-between;align-items:baseline;font-size:12px;margin-bottom:6px">
        <span style="color:{sell_c};font-weight:600">Sell {sell_pct:.0f}%</span>
        <span style="color:{M_MUTED};font-size:11px;text-transform:uppercase;letter-spacing:0.08em">{subtitle}</span>
        <span style="color:{buy_c};font-weight:600">Buy {buy_pct:.0f}%</span>
      </div>
      <div class="m-gauge-wrap">
        <div class="m-gauge-sell" style="width:{sell_pct}%"></div>
        <div class="m-gauge-buy"  style="width:{buy_pct}%"></div>
      </div>
      <div style="text-align:center;font-size:12px;color:{label_c};margin-top:8px;font-weight:500">
        {label}
      </div>
    </div>"""


def stat_card_html(label: str, value: str, sub: str = "", small: bool = False) -> str:
    """Ramp-style stat: small uppercase eyebrow + huge tabular number + tiny sub."""
    cls = "num small" if small else "num"
    sub_html = f"<p class='sub'>{sub}</p>" if sub else ""
    return (
        f"<div class='m-stat'>"
        f"<p class='label'>{label}</p>"
        f"<p class='{cls}'>{value}</p>"
        f"{sub_html}"
        f"</div>"
    )


def predict_pattern(row: pd.Series, flow_df: pd.DataFrame):
    """Return (signal, color, buy_pct, reasons) based on foreign net flow signals."""
    net_1d  = safe_float(row.get("net_flow_1d",  0))
    net_3d  = safe_float(row.get("net_flow_3d",  0))
    net_5d  = safe_float(row.get("net_flow_5d",  0))
    net_10d = safe_float(row.get("net_flow_10d", 0))
    streak  = int(safe_float(row.get("accum_streak", 0)))

    rate_3d  = net_3d  / 3  if net_3d  != 0 else 0.0
    rate_10d = net_10d / 10 if net_10d != 0 else 0.0

    score = 0
    reasons: list[str] = []

    # Short-term direction
    if net_1d > 0 and rate_3d > 0:
        score += 2
        reasons.append(f"Net inflow last 3 days (+{net_3d/1e6:.1f}M shares)")
    elif net_1d < 0 and rate_3d < 0:
        score -= 2
        reasons.append(f"Net outflow last 3 days ({net_3d/1e6:.1f}M shares)")

    # Sustained direction
    rate_5d = net_5d / 5 if net_5d != 0 else 0.0
    if rate_5d > 0 and rate_10d > 0:
        score += 2
        reasons.append(f"Sustained 10-day inflow (+{net_10d/1e6:.1f}M total)")
    elif rate_5d < 0 and rate_10d < 0:
        score -= 2
        reasons.append(f"Sustained 10-day outflow ({net_10d/1e6:.1f}M total)")

    # Accumulation streak
    if streak >= 5:
        score += 2
        reasons.append(f"{streak}-day consecutive foreign accumulation")
    elif streak >= 3:
        score += 1
        reasons.append(f"{streak}-day accumulation streak")

    # Acceleration vs 10-day baseline
    if rate_10d != 0:
        accel = (net_1d - rate_10d) / (abs(rate_10d) + 1e-9)
        if accel > 0.5 and net_1d > 0:
            score += 1
            reasons.append("Inflow accelerating above 10-day average")
        elif accel < -0.5 and net_1d < 0:
            score -= 1
            reasons.append("Outflow accelerating below 10-day average")

    # 5-day buy concentration from live IDX-API data
    buy_pct = 50.0
    if not flow_df.empty:
        recent = flow_df.head(5)
        total_buy  = recent["foreign_buy"].sum()
        total_sell = recent["foreign_sell"].sum()
        total = total_buy + total_sell
        if total > 0:
            buy_pct = float(total_buy / total * 100)

    if score >= 4:
        return "STRONG ACCUMULATION", "#00C853", buy_pct, reasons
    if score >= 2:
        return "ACCUMULATING", "#64DD17", buy_pct, reasons
    if score >= 0:
        return "NEUTRAL", "#78909C", buy_pct, reasons
    if score >= -2:
        return "DISTRIBUTING", "#FF6D00", buy_pct, reasons
    return "STRONG DISTRIBUTION", "#FF1744", buy_pct, reasons


# ── Auto-run on visit ─────────────────────────────────────────────────────────
_auto_placeholder = st.empty()
with _auto_placeholder.container():
    with st.spinner("Checking today's scores…"):
        try:
            ensure_today_scored(CONFIG_PATH)
        except Exception as _e:
            st.warning(f"Auto-scoring skipped: {_e}")
_auto_placeholder.empty()


# ── Onboarding popup (first visit) ────────────────────────────────────────────
if not st.session_state.onboarding_done:
    st.markdown(
        f"""
        <div class="m-onboard">
          <p class="m-eyebrow" style="color:{M_MUTED};font-size:11px;
              text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">
            Welcome to Mantra
          </p>
          <h2>Here's what you're looking at.</h2>
          <p>
            Mantra processes every listed stock on the IDX each night and ranks
            them by order flow conviction. Start with <b>INVEST</b> and
            <b>WATCH_EXEC</b>. INVEST means the accumulation signal is confirmed
            and price is beginning to move on volume. WATCH_EXEC means the
            signal is clearly present but price hasn't moved yet. That's the
            setup.
          </p>
          <p>
            Check the Broker Anomaly score on anything that looks interesting.
            A score above 70 alongside an INVEST label means two independent
            statistical methods are confirming the same thing. That's the
            highest-conviction output the system generates.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _ob_a, _ob_b, _ = st.columns([1, 1, 4])
    with _ob_a:
        if st.button("Open the screener", type="secondary", use_container_width=True):
            st.session_state.onboarding_done = True
            st.rerun()
    with _ob_b:
        st.link_button(
            "Read the methodology",
            url="/White_Paper",
            use_container_width=True,
        )
    st.stop()

# ── Stale-data banner ─────────────────────────────────────────────────────────
# IDX trades Mon-Fri; on a normal weekday after market close the DB should
# contain T or T-1. Anything older means the daily refresh job didn't run
# (see scripts/SETUP_VPS_REFRESH.md).
_latest_db_date = latest_idx_trading_date(CONFIG_PATH)
if _latest_db_date:
    _today = pd.Timestamp.now(tz="Asia/Jakarta").normalize().tz_localize(None)
    _latest_ts = pd.Timestamp(_latest_db_date)
    _business_gap = len(pd.bdate_range(_latest_ts, _today)) - 1  # exclude latest itself
    if _business_gap >= 2:
        st.warning(
            f"⚠️ Data is stale — latest IDX trading day in the DB is **{_latest_db_date}** "
            f"({_business_gap} business days behind). The daily refresh job hasn't run. "
            f"On the host: `./scripts/daily_refresh.sh` (see `scripts/SETUP_VPS_REFRESH.md`)."
        )

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<div style='font-size:22px;font-weight:700;letter-spacing:-0.02em;"
        f"margin:4px 0 2px 0;color:{M_TEXT}'>Mantra</div>"
        f"<div style='color:{M_MUTED};font-size:12px;margin-bottom:18px;line-height:1.5'>"
        f"Broker-flow screener for the Indonesian stock market.</div>",
        unsafe_allow_html=True,
    )

    available_dates = cached_available_dates(CONFIG_PATH)
    if not available_dates:
        st.error("No scored dates found — check your IDX database path in config.json.")
        st.stop()

    # Calendar picker constrained to dates we actually have scores for
    _date_objs = [pd.to_datetime(d).date() for d in available_dates]
    _picked = st.date_input(
        "Scoring date",
        value=_date_objs[0],
        min_value=min(_date_objs),
        max_value=max(_date_objs),
        format="YYYY-MM-DD",
    )
    if str(_picked) not in available_dates:
        # Fallback to nearest available date
        _picked = min(_date_objs, key=lambda d: abs(d - _picked))
        st.caption(f"No data for selected date — showing closest: {_picked}")
    selected_date = str(_picked)

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    min_invest = st.slider("Min investment score", 0, 100, 0)
    min_adv_b = st.slider(
        "Min avg daily value (IDR billion)",
        min_value=0.0,
        max_value=50.0,
        value=0.0,
        step=0.5,
        help="Filter out illiquid tickers. 1 = 1 billion IDR average daily traded value.",
    )
    only_breakout = st.checkbox("Breakout signals only", value=False)
    selected_actions = ["INVEST", "WATCH_EXEC", "WATCH", "OBSERVE", "AVOID"]

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # Dark mode toggle (drives the CSS injection at the top of this script).
    st.toggle(":material/dark_mode: Dark mode", key="dark_mode")

    if st.button(":material/help: How this works", use_container_width=True):
        st.session_state.onboarding_done = False
        st.rerun()


# ── Load & filter data ────────────────────────────────────────────────────────
df = cached_scores_for_date(selected_date, CONFIG_PATH)
if df.empty:
    st.warning(f"No data found for {selected_date}.")
    st.stop()

stage2_only = "broker_data_source" in df.columns
mask = (
    df["action"].isin(selected_actions)
    & (df["investment_score"] >= min_invest)
)
if min_adv_b > 0 and "avg_daily_value_idr" in df.columns:
    mask = mask & (df["avg_daily_value_idr"].fillna(0) >= min_adv_b * 1e9)
if stage2_only:
    mask = mask & (df["broker_data_source"] == "indexalpha")
if only_breakout and "breakout_signal" in df.columns:
    mask = mask & df["breakout_signal"].fillna(False).astype(bool)
filtered = df[mask].copy().reset_index(drop=True)


# ── Header row ────────────────────────────────────────────────────────────────
st.markdown(
    f"<p class='m-eyebrow' style='color:{M_MUTED};font-size:11px;text-transform:uppercase;"
    f"letter-spacing:0.08em;margin:4px 0 6px 0'>IDX Screener · {selected_date}</p>"
    f"<h1 style='font-size:44px;margin:0 0 4px 0;font-weight:700;letter-spacing:-0.03em'>Mantra</h1>"
    f"<p style='color:{M_MUTED};font-size:15px;margin:0 0 28px 0'>"
    f"{len(df):,} tickers scored · {len(filtered):,} match the current filters</p>",
    unsafe_allow_html=True,
)


# ── Rankings table ────────────────────────────────────────────────────────────
st.markdown(
    f"<p class='m-eyebrow' style='color:{M_MUTED};font-size:11px;text-transform:uppercase;"
    f"letter-spacing:0.08em;margin:0 0 4px 0'>Rankings</p>"
    f"<h3 style='font-size:22px;margin:0 0 4px 0'>Top 100 by broker signal strength</h3>"
    f"<p style='color:{M_MUTED};font-size:13px;margin:0 0 16px 0'>"
    f"Validated with real broker flow data and Isolation Forest anomaly detection.</p>",
    unsafe_allow_html=True,
)

_rank_cols = [
    "ticker", "company_name", "action",
    "investment_score", "breakout_signal",
    "broker_flow_real_score",
    "float_pressure_score", "structure_score",
    "liquidity_score", "catalyst_score",
    "ff_category", "avg_daily_value_idr", "close",
]
rank_cols = [c for c in _rank_cols if c in filtered.columns]
rank_df = filtered[rank_cols].copy().reset_index(drop=True)
rank_df.index = rank_df.index + 1
rank_df.index.name = "Rank"

if "company_name" in rank_df.columns:
    rank_df["company_name"] = rank_df["company_name"].str.slice(0, 30)

score_cols = [c for c in rank_cols if c.endswith("_score")]

fmt_map: dict = {c: "{:.1f}" for c in score_cols}
fmt_map["avg_daily_value_idr"] = "{:,.0f}"
if "close" in rank_df.columns:
    fmt_map["close"] = lambda v: fmt(v, ",.0f")


def _color_action_cell(v: str) -> str:
    c = ACTION_COLORS.get(str(v), "#78909C")
    return f"color: {c}; font-weight: bold"


def _color_score_bg(v) -> str:
    try:
        pct = float(v)
    except (TypeError, ValueError):
        return ""
    # Ramp-style: 10% opacity background, dark accessible text colour.
    if pct >= 70:   return "background-color: #D1FAE5; color: #065F46; font-weight:500"
    if pct >= 55:   return "background-color: #FEF9C3; color: #854D0E; font-weight:500"
    if pct >= 40:   return "background-color: #FFEDD5; color: #9A3412; font-weight:500"
    return "background-color: #FEE2E2; color: #991B1B; font-weight:500"


score_subset = [c for c in ["investment_score", "broker_flow_real_score", "broker_flow_score"] if c in rank_df.columns]
styled_rank = (
    rank_df.style
    .map(_color_action_cell, subset=["action"])
    .map(_color_score_bg, subset=score_subset)
    .format(fmt_map, na_rep="—")
)
st.dataframe(styled_rank, width="stretch", height=430)


# ── Ticker detail panel ───────────────────────────────────────────────────────
st.divider()
st.markdown("### Ticker Detail")

# Constrain ticker selector to the visible (filtered) rankings table only.
ticker_list = filtered["ticker"].tolist()
if not ticker_list:
    st.info("No tickers match the current filters. Adjust the sidebar filters.")
    st.stop()

selected_ticker = st.selectbox(
    "Select ticker",
    ticker_list,
    key="ticker_sel",
    help="Only tickers shown in the rankings table above are selectable.",
)
row = df[df["ticker"] == selected_ticker].iloc[0]

# Load flow data once (cached — used in Broker Analysis and Price tabs)
flow_df = cached_ticker_flow(selected_ticker, CONFIG_PATH, days=30)

# Load config weights once for display
from src.config import Config as _Cfg
_cfg_weights = _Cfg.load(CONFIG_PATH).weights

# Ticker header card — Ramp-style: big ticker, action pill, side stats
action_val   = str(row.get("action", "—"))
inv_score    = safe_float(row.get("investment_score", 0))
breakout     = bool(row.get("breakout_signal", False))
company      = str(row.get("company_name", selected_ticker))
if company == selected_ticker:
    company = ""

close_disp   = fmt(row.get("close"), ",.0f")
avg_idr      = safe_float(row.get("avg_daily_value_idr", 0))
avg_idr_disp = f"{avg_idr/1e9:.1f}B" if avg_idr else "N/A"
inv_color    = score_color(inv_score)
breakout_lbl = "Confirmed" if breakout else "Pending"
breakout_clr = "#16A34A" if breakout else M_MUTED

st.markdown(
    f"""
    <div class="m-card" style="padding:28px 32px">
      <div style="display:flex;align-items:flex-start;gap:24px;flex-wrap:wrap">
        <div style="flex:1 1 240px">
          <p class="m-eyebrow" style="color:{M_MUTED};font-size:11px;text-transform:uppercase;
              letter-spacing:0.08em;margin:0 0 4px 0">Ticker</p>
          <div style="font-size:48px;font-weight:700;line-height:1;letter-spacing:-0.03em;
              color:{M_TEXT}">{selected_ticker}</div>
          <div style="color:{M_MUTED};font-size:13px;margin-top:6px">{company}</div>
          <div style="margin-top:14px">{action_badge_html(action_val)}</div>
        </div>
        <div style="display:flex;gap:36px;flex-wrap:wrap">
          <div>
            <p class="m-eyebrow" style="color:{M_MUTED};font-size:11px;text-transform:uppercase;
                letter-spacing:0.08em;margin:0 0 4px 0">Investment score</p>
            <div style="font-size:32px;font-weight:700;color:{inv_color};line-height:1;
                font-variant-numeric:tabular-nums">{inv_score:.1f}</div>
          </div>
          <div>
            <p class="m-eyebrow" style="color:{M_MUTED};font-size:11px;text-transform:uppercase;
                letter-spacing:0.08em;margin:0 0 4px 0">Breakout</p>
            <div style="font-size:18px;font-weight:600;color:{breakout_clr};line-height:1.6">
              {breakout_lbl}</div>
          </div>
          <div>
            <p class="m-eyebrow" style="color:{M_MUTED};font-size:11px;text-transform:uppercase;
                letter-spacing:0.08em;margin:0 0 4px 0">Close (IDR)</p>
            <div style="font-size:18px;font-weight:600;color:{M_TEXT};line-height:1.6;
                font-variant-numeric:tabular-nums">{close_disp}</div>
          </div>
          <div>
            <p class="m-eyebrow" style="color:{M_MUTED};font-size:11px;text-transform:uppercase;
                letter-spacing:0.08em;margin:0 0 4px 0">Avg daily value</p>
            <div style="font-size:18px;font-weight:600;color:{M_TEXT};line-height:1.6;
                font-variant-numeric:tabular-nums">{avg_idr_disp}</div>
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_scores, tab_broker, tab_price, tab_history = st.tabs(
    ["📊 Scores", "🏦 Broker Analysis", "📈 Price & Volume", "📅 History"]
)


# ── Tab 1: Scores ─────────────────────────────────────────────────────────────
with tab_scores:
    col_inv, col_exec = st.columns(2)

    with col_inv:
        st.markdown("**Investment Sub-scores**")
        w = _cfg_weights
        # Use real broker flow score for Stage 2 tickers; never show the proxy.
        bf_score_val = safe_float(
            row.get("broker_flow_real_score") if row.get("broker_data_source") == "indexalpha"
            else row.get("broker_flow_score", 0)
        )
        st.markdown(subscore_bar("Broker Flow (real)", f"×{w.broker_flow:.2f}", bf_score_val), unsafe_allow_html=True)
        for col_key, label, weight in [
            ("float_pressure_score", "Float Pressure", f"×{w.float_pressure:.2f}"),
            ("structure_score",      "Structure",      f"×{w.structure:.2f}"),
            ("liquidity_score",      "Liquidity",      f"×{w.liquidity:.2f}"),
            ("catalyst_score",       "Catalyst (info)",f"×{w.catalyst:.2f}"),
        ]:
            v = safe_float(row.get(col_key, 0))
            st.markdown(subscore_bar(label, weight, v), unsafe_allow_html=True)

    with col_exec:
        st.markdown("**Real Broker Flow Signals**")
        is_real = row.get("broker_data_source") == "indexalpha"
        if is_real:

            retail_ss  = safe_float(row.get("retail_sell_share", 0)) * 100
            absorption = safe_float(row.get("absorption_ratio", 0))
            streak     = int(safe_float(row.get("accum_streak", 0)))
            xl_trend   = bool(row.get("xl_xc_trend_selling", False))
            xl_days    = int(safe_float(row.get("xl_xc_trend_days", 0)))
            xl_selling = bool(row.get("xl_xc_selling", False))
            xl_buying  = bool(row.get("xl_xc_buying", False))

            # Each row: (label, value, description shown as small text)
            signal_rows = [
                (
                    "Retail selling pressure",
                    f"{retail_ss:.1f}% of volume",
                    "Share of 20-day volume that is retail net selling. Higher means more retail investors are exiting this stock.",
                ),
                (
                    "Institutional absorption",
                    f"{absorption:.2f}×",
                    "How much of retail selling is being absorbed by institutional brokers. Above 1× means institutions buy more than retail sells — float is tightening.",
                ),
                (
                    "Institutional accumulation streak",
                    f"{streak} consecutive day{'s' if streak != 1 else ''}",
                    "How many days in a row institutional brokers (investment banks, market makers, emitents) have been net buyers.",
                ),
            ]
            if xl_selling:
                signal_rows.append((
                    "Retail trend today (Stockbit / Ajaib / Mirae)",
                    "⚡ Net selling — bullish signal",
                    "Stockbit (XL), Ajaib (XC) and/or Mirae (YP) are net sellers today. Retail is exiting. When institutions simultaneously absorb this, it is a bullish divergence.",
                ))
            if xl_buying:
                signal_rows.append((
                    "Retail trend today (Stockbit / Ajaib / Mirae)",
                    "⚠️ Net buying — bearish signal",
                    "Stockbit (XL), Ajaib (XC) and/or Mirae (YP) are net buyers today. Retail is piling in, which often signals institutions are distributing into retail demand.",
                ))
            if xl_trend and xl_days >= 3:
                signal_rows.append((
                    "Retail exit trend (Stockbit / Ajaib / Mirae)",
                    f"🚨 {xl_days} of last 10 trading days",
                    f"Retail platforms have been net sellers on {xl_days} of the last 10 days — a sustained trend, not a one-day blip. Bullish if institutions are absorbing.",
                ))

            for label, value, desc in signal_rows:
                st.markdown(
                    f"<div style='padding:12px 0;border-bottom:1px solid {M_BORDER}'>"
                    f"  <div style='display:flex;justify-content:space-between;align-items:baseline;font-size:14px'>"
                    f"    <span style='color:{M_TEXT}'>{label}</span>"
                    f"    <b style='margin-left:12px;white-space:nowrap;font-variant-numeric:tabular-nums'>{value}</b>"
                    f"  </div>"
                    f"  <div style='color:{M_MUTED};font-size:12px;margin-top:4px;line-height:1.5'>{desc}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            sust = str(row.get("sustained_buyers", "")).strip()
            if sust and sust != "nan":
                st.markdown("")
                st.markdown(f"**Buying above their own average (z ≥ 1.5):** {sust}")
                st.caption("See the Broker Analysis tab for the full top buyers / sellers breakdown.")
        else:
            st.info("This ticker is not in the Stage 2 top 100 — only a proxy score is available.")


# ── Tab 2: Broker Distribution ────────────────────────────────────────────────
with tab_broker:
    broker_names = cached_broker_names(CONFIG_PATH)

    # Controls row
    bc1, bc2 = st.columns([2, 1])
    with bc1:
        investor_type = st.radio(
            "Investor type",
            options=["all", "f", "d"],
            format_func=lambda x: {"all": "All Investors", "f": "Foreign Only", "d": "Domestic Only"}[x],
            horizontal=True,
            key="broker_investor",
        )
    with bc2:
        broker_date = st.date_input(
            "Date",
            value=pd.to_datetime(selected_date).date(),
            key="broker_date",
        )

    broker_date_str = str(broker_date)

    # Fetch data (cached locally after first call)
    bdf, api_error = cached_broker_summary(selected_ticker, broker_date_str, investor_type, CONFIG_PATH)

    if api_error:
        st.error(f"API error: {api_error}")
        st.stop()

    if bdf.empty:
        st.info(f"No broker data for {selected_ticker} on {broker_date_str}. "
                "Try a different date — weekends and public holidays have no data.")
    else:
        # ── Enrich ────────────────────────────────────────────────────────────
        bdf["name"]        = bdf["code"].map(broker_names).fillna(bdf["code"])
        bdf["net_vol_m"]   = (bdf["buy_volume"].fillna(0) - bdf["sell_volume"].fillna(0)) / 1e6
        bdf["buy_vol_m"]   = bdf["buy_volume"].fillna(0) / 1e6
        bdf["sell_vol_m"]  = bdf["sell_volume"].fillna(0) / 1e6
        bdf["net_value_b"] = bdf["net_value"] / 1e9

        total_buy_vol  = bdf["buy_volume"].fillna(0).sum()
        total_sell_vol = bdf["sell_volume"].fillna(0).sum()
        total_net_vol  = total_buy_vol - total_sell_vol
        total_vol      = total_buy_vol + total_sell_vol

        # % of total net volume per broker (signed: positive = net buyer)
        bdf["net_vol_pct"] = (bdf["net_vol_m"] * 1e6 / total_vol * 100) if total_vol > 0 else 0.0

        # ── Gauge: depends on investor_type ──────────────────────────────────
        SIGNAL_CLASSES = {"institutional", "Market_Maker", "Emitent", "Zombie"}
        RETAIL_CLASSES  = {"retail_pure", "retail_mixed"}

        inst_net = retail_net = 0.0
        if investor_type == "all":
            # Total buy ≡ total sell → useless. Use smart money vs retail net instead.
            bm = cached_broker_master(CONFIG_PATH)
            bdf_cls = bdf.merge(bm, left_on="code", right_on="broker_code", how="left")
            bdf_cls["broker_class"] = bdf_cls["broker_class"].fillna("unknown")
            bdf_cls["net_vol"] = bdf_cls["buy_volume"].fillna(0) - bdf_cls["sell_volume"].fillna(0)

            inst_net   = float(bdf_cls[bdf_cls["broker_class"].isin(SIGNAL_CLASSES)]["net_vol"].sum())
            retail_net = float(bdf_cls[bdf_cls["broker_class"].isin(RETAIL_CLASSES)]["net_vol"].sum())

            eps = 1e-9
            buy_pct_all = float(50 + (inst_net / (total_vol + eps)) * 300)
            buy_pct_all = max(0.0, min(100.0, buy_pct_all))
            gauge_subtitle = "institutional net vs retail net"
        else:
            buy_pct_all = total_buy_vol / total_vol * 100 if total_vol > 0 else 50.0
            gauge_subtitle = "foreign buy vs sell" if investor_type == "f" else "domestic buy vs sell"

        # ── Summary metrics ───────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        if investor_type == "all":
            m1.metric("Institutional Net", f"{inst_net/1e6:+.2f}M lots",
                      help="Net volume of institutional/MM/Emitent/Zombie brokers. Positive = net buying.")
            m2.metric("Retail Net",        f"{retail_net/1e6:+.2f}M lots",
                      help="Net volume of retail brokers (retail_pure, retail_mixed). Negative = net selling.")
        else:
            m1.metric("Total Buy Volume", f"{total_buy_vol/1e6:.1f}M lots")
            m2.metric("Total Sell Volume", f"{total_sell_vol/1e6:.1f}M lots")
        m3.metric("Total Volume", f"{total_vol/1e6:.1f}M lots")
        m4.metric("Brokers Active", len(bdf))

        st.markdown(concentration_gauge(buy_pct_all, gauge_subtitle), unsafe_allow_html=True)
        st.divider()

        # ── Net accumulation chart — sorted by net volume ─────────────────────
        st.markdown(
            f"<h4 style='font-size:18px;margin:24px 0 8px 0'>Net volume by broker</h4>"
            f"<p style='color:{M_MUTED};font-size:13px;margin:0 0 12px 0'>"
            f"Green = net buyer · Red = net seller</p>",
            unsafe_allow_html=True,
        )

        chart_df = bdf.nlargest(20, "buy_volume")[["code", "net_vol_m"]].copy()
        chart_df = chart_df.sort_values("net_vol_m", ascending=True)

        net_bar = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                y=alt.Y("code:N", sort=None, title=None),
                x=alt.X("net_vol_m:Q", title="Net Volume (M lots)"),
                color=alt.condition(
                    alt.datum["net_vol_m"] > 0,
                    alt.value(ALTAIR_GREEN),
                    alt.value(ALTAIR_RED),
                ),
                tooltip=[
                    alt.Tooltip("code:N", title="Broker"),
                    alt.Tooltip("net_vol_m:Q", title="Net Vol (M)", format="+.2f"),
                ],
            )
            .properties(height=max(200, len(chart_df) * 22))
        )
        st.altair_chart(net_bar, width="stretch")
        st.divider()

        # ── Top Net Buyers / Top Net Sellers ──────────────────────────────────
        def _net_color(v: float) -> str:
            if v > 0: return "color: #16A34A; font-weight:600"
            if v < 0: return "color: #DC2626; font-weight:600"
            return f"color: {M_MUTED}"

        # Sort by actual buy/sell volume — not net — so the tables answer
        # "who bought the most?" and "who sold the most?" clearly
        top_buyers = (
            bdf.nlargest(10, "buy_vol_m")
            [["code", "name", "buy_vol_m", "sell_vol_m", "net_vol_m"]]
            .copy()
        )
        top_sellers = (
            bdf.nlargest(10, "sell_vol_m")
            [["code", "name", "buy_vol_m", "sell_vol_m", "net_vol_m"]]
            .copy()
        )

        col_buy, col_sell = st.columns(2)
        tbl_fmt = {"Buy (M lots)": "{:.2f}", "Sell (M lots)": "{:.2f}", "Net (M lots)": "{:+.2f}"}

        with col_buy:
            st.markdown(
                f"<h4 style='font-size:16px;margin:8px 0 4px 0;color:#16A34A'>Top buyers</h4>"
                f"<p style='color:{M_MUTED};font-size:12px;margin:0 0 8px 0'>by buy volume</p>",
                unsafe_allow_html=True,
            )
            top_buyers.columns = ["Code", "Broker", "Buy (M lots)", "Sell (M lots)", "Net (M lots)"]
            st.dataframe(
                top_buyers.style
                .map(_net_color, subset=["Net (M lots)"])
                .format(tbl_fmt),
                hide_index=True, width="stretch", height=340,
            )

        with col_sell:
            st.markdown(
                f"<h4 style='font-size:16px;margin:8px 0 4px 0;color:#DC2626'>Top sellers</h4>"
                f"<p style='color:{M_MUTED};font-size:12px;margin:0 0 8px 0'>by sell volume</p>",
                unsafe_allow_html=True,
            )
            top_sellers.columns = ["Code", "Broker", "Buy (M lots)", "Sell (M lots)", "Net (M lots)"]
            st.dataframe(
                top_sellers.style
                .map(_net_color, subset=["Net (M lots)"])
                .format(tbl_fmt),
                hide_index=True, width="stretch", height=340,
            )

        st.divider()

        # ── Watchlist Z-score anomaly detection ───────────────────────────────
        from src.config import Config as _Cfg
        _watchlist = _Cfg.load(CONFIG_PATH).broker_watchlist or []

        st.markdown("#### Watchlist Broker Anomalies")
        _aw_col, _sw_col = st.columns(2)
        with _aw_col:
            _window_label = st.selectbox(
                "Baseline window",
                options=["1 week (5d)", "2 weeks (10d)", "1 month (22d)"],
                index=2,
                key="anomaly_window",
            )
        with _sw_col:
            _signal_label = st.selectbox(
                "Compare period",
                options=["Today", "3 days", "5 days"],
                index=0,
                key="anomaly_signal",
            )

        _window_days = {"1 week (5d)": 5, "2 weeks (10d)": 10, "1 month (22d)": 22}[_window_label]
        _signal_days = {"Today": 1, "3 days": 3, "5 days": 5}[_signal_label]
        _min_history = max(5, _window_days // 2)

        if not _watchlist:
            st.info("Add broker codes to `broker_watchlist` in config.json to enable anomaly detection.")
        else:
            # Fetch enough days to cover both signal period and baseline
            _hist_dates = tuple(str(d) for d in pd.bdate_range(
                end=broker_date_str, periods=_window_days + _signal_days + 2
            ).strftime("%Y-%m-%d").tolist())

            _hist = cached_broker_history(
                selected_ticker,
                _hist_dates,
                investor_type,
                CONFIG_PATH,
            )

            _days_cached = _hist["date"].nunique() if not _hist.empty else 0
            _days_needed = _min_history + _signal_days

            if _hist.empty or _days_cached < _days_needed:
                st.info(
                    f"Need at least {_days_needed} days cached for "
                    f"**{_signal_label}** vs **{_window_label}**. "
                    f"Have {_days_cached} day(s).  \n"
                    "Each date you view in Broker Analysis gets cached automatically."
                )
            else:
                import numpy as np
                from src.anomaly import score_brokers

                _hist_wl = _hist[_hist["code"].isin(_watchlist)].copy()

                # Signal period: last _signal_days business days up to broker_date_str
                _signal_dates = pd.bdate_range(
                    end=broker_date_str, periods=_signal_days
                ).strftime("%Y-%m-%d").tolist()
                _signal_start = _signal_dates[0]

                # Baseline: all history BEFORE the signal period (unbiased)
                _baseline = _hist_wl[_hist_wl["date"] < _signal_start]

                # Signal DataFrame: rows for the signal period
                if _signal_days == 1:
                    _today_wl = bdf[bdf["code"].isin(_watchlist)].copy()
                    _today_wl["date"] = broker_date_str
                    _signal_df = _today_wl
                else:
                    _signal_df = _hist_wl[_hist_wl["date"].isin(_signal_dates)].copy()

                # Mean net_volume per broker over signal period (for z-score)
                _signal_by_code = (
                    _signal_df.groupby("code")["net_volume"].mean().to_dict()
                )

                # ── Isolation Forest scores ───────────────────────────────────
                _if_scores = score_brokers(_baseline, _signal_df)
                _if_map = _if_scores.set_index("code")["anomaly_score"].to_dict() if not _if_scores.empty else {}
                _if_label_map = _if_scores.set_index("code")["if_label"].to_dict() if not _if_scores.empty else {}

                # ── Z-score + IF combined table ───────────────────────────────
                _baseline_days = _baseline["date"].nunique() if not _baseline.empty else 0
                st.caption(
                    f"Comparing {_signal_label} of activity against {_baseline_days}-day historical baseline. "
                    f"Flagged when a broker's net volume is unusually high (z-score ≥ 1.5) or the Isolation Forest model marks it as anomalous."
                )

                alerts = []
                for code, signal_net in _signal_by_code.items():
                    hist_broker = _baseline[_baseline["code"] == code]["net_volume"]
                    if len(hist_broker) < _min_history:
                        continue

                    # Z-score
                    mean = hist_broker.mean()
                    std  = hist_broker.std()
                    z    = (signal_net - mean) / std if std > 1 else 0.0

                    # IF score
                    if_score = _if_map.get(code)
                    if_flagged = (_if_label_map.get(code) == -1)

                    # Include if flagged by either method
                    if abs(z) < 1.5 and not if_flagged:
                        continue

                    name = broker_names.get(code, code)
                    direction = "🟢 BUYING" if signal_net > 0 else "🔴 SELLING"
                    alerts.append({
                        "Broker":                           f"{code} — {name}",
                        f"Signal [{_signal_label}] (M)":   signal_net / 1e6,
                        f"Baseline [{_window_label}] (M)": mean / 1e6,
                        "Z-Score":                          z,
                        "IF Score":                         if_score if if_score is not None else "—",
                        "Direction":                        direction,
                    })

                if not alerts:
                    st.success(
                        f"No anomalies — {_signal_label} activity is within the {_window_label} baseline."
                    )
                else:
                    alerts_df = pd.DataFrame(alerts).sort_values(
                        "Z-Score", key=lambda s: s.abs() if s.dtype != object else s.fillna(0).abs(),
                        ascending=False,
                    )
                    sig_col  = f"Signal [{_signal_label}] (M)"
                    base_col = f"Baseline [{_window_label}] (M)"

                    def _if_color(v) -> str:
                        try:
                            score = float(v)
                            if score >= 70: return "background-color:#FEE2E2;color:#991B1B;font-weight:600"
                            if score >= 50: return "background-color:#FFEDD5;color:#9A3412;font-weight:500"
                        except (TypeError, ValueError):
                            pass
                        return ""

                    num_if = [c for c in [sig_col, base_col, "Z-Score"] if c in alerts_df.columns]
                    st.dataframe(
                        alerts_df.style
                        .map(_net_color, subset=num_if)
                        .map(_if_color,  subset=["IF Score"])
                        .format({
                            sig_col:   "{:+.2f}",
                            base_col:  "{:+.2f}",
                            "Z-Score": "{:+.1f}",
                        }, na_rep="—"),
                        hide_index=True,
                        width="stretch",
                    )

                    st.caption(
                        "**IF Score**: 0–100, higher = more anomalous per Isolation Forest  ·  "
                        "🔴 ≥ 70 strong anomaly  ·  🟠 ≥ 50 moderate"
                    )

                # ── IF anomaly score chart (all watchlist brokers) ────────────
                if not _if_scores.empty:
                    st.markdown("**Isolation Forest — All Watchlist Brokers**")
                    _chart_df = _if_scores.copy()
                    _chart_df["name"] = _chart_df["code"].map(broker_names).fillna(_chart_df["code"])
                    _chart_df["label"] = _chart_df["code"] + " — " + _chart_df["name"].str.slice(0, 20)
                    _chart_df["color"] = _chart_df.apply(
                        lambda r: ALTAIR_RED if r["direction"] == "selling"
                        else ALTAIR_GREEN if r["direction"] == "buying"
                        else ALTAIR_NEUTRAL,
                        axis=1,
                    )
                    _chart_df = _chart_df.sort_values("anomaly_score", ascending=True)

                    _if_bar = (
                        alt.Chart(_chart_df)
                        .mark_bar()
                        .encode(
                            y=alt.Y("label:N", sort=None, title=None),
                            x=alt.X(
                                "anomaly_score:Q",
                                title="IF Anomaly Score (0–100)",
                                scale=alt.Scale(domain=[0, 100]),
                            ),
                            color=alt.Color(
                                "color:N",
                                scale=None,
                                legend=alt.Legend(
                                    title="Direction",
                                    values=[ALTAIR_GREEN, ALTAIR_RED, ALTAIR_NEUTRAL],
                                    labelExpr=(
                                        f"datum.value === '{ALTAIR_GREEN}' ? 'Buying' : "
                                        f"datum.value === '{ALTAIR_RED}' ? 'Selling' : 'Neutral'"
                                    ),
                                ),
                            ),
                            tooltip=[
                                alt.Tooltip("code:N", title="Broker"),
                                alt.Tooltip("anomaly_score:Q", title="IF Score", format=".1f"),
                                alt.Tooltip("direction:N", title="Direction"),
                            ],
                        )
                        .properties(height=max(150, len(_chart_df) * 28))
                    )

                    # Reference lines at 50 and 70
                    _ref = pd.DataFrame([{"x": 50, "label": "Moderate"}, {"x": 70, "label": "Strong"}])
                    _ref_lines = (
                        alt.Chart(_ref)
                        .mark_rule(strokeDash=[4, 4], opacity=0.6)
                        .encode(
                            x="x:Q",
                            color=alt.Color(
                                "label:N",
                                scale=alt.Scale(
                                    domain=["Moderate", "Strong"],
                                    range=["#EA580C", ALTAIR_RED],
                                ),
                            ),
                        )
                    )

                    st.altair_chart(_if_bar + _ref_lines, width="stretch")
                    st.caption("Green = net buying anomaly · Red = net selling anomaly · Dashed lines: 50 (moderate), 70 (strong)")


# ── Tab 3: Price & Volume ─────────────────────────────────────────────────────
with tab_price:
    if not flow_df.empty:
        price_df = flow_df.copy()
        price_df["Date"]   = pd.to_datetime(price_df["date"].astype(str))
        price_df = price_df.sort_values("Date")

        close_line = (
            alt.Chart(price_df)
            .mark_line(color=ALTAIR_GREEN, strokeWidth=2)
            .encode(
                x=alt.X("Date:T", title=None),
                y=alt.Y("close:Q", title="Close (IDR)", scale=alt.Scale(zero=False)),
                tooltip=["Date:T", alt.Tooltip("close:Q", format=",.0f", title="Close")],
            )
            .properties(height=220, title=f"{selected_ticker} — Close Price")
        )

        vol_bar = (
            alt.Chart(price_df)
            .mark_bar(color=ALTAIR_NEUTRAL, opacity=0.6)
            .encode(
                x=alt.X("Date:T", title=None),
                y=alt.Y("volume:Q", title="Volume"),
                tooltip=["Date:T", alt.Tooltip("volume:Q", format=",.0f", title="Volume")],
            )
            .properties(height=110, title="Volume")
        )

        st.altair_chart(
            alt.vconcat(close_line, vol_bar).resolve_scale(x="shared"),
            width="stretch",
        )

        # Summary row
        latest_px = price_df.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Close",    fmt(latest_px.get("close")))
        c2.metric("Volume",   fmt(latest_px.get("volume")))
        h20 = price_df["high"].max() if "high" in price_df.columns else None
        l20 = price_df["low"].min()  if "low"  in price_df.columns else None
        c3.metric("20-day High", fmt(h20))
        c4.metric("20-day Low",  fmt(l20))

    else:
        # Fallback to scores CSV data
        c1, c2, c3 = st.columns(3)
        c1.metric("Close",  fmt(row.get("close")))
        c2.metric("Volume", fmt(row.get("volume")))
        c3.metric("Vol Ratio ×20d avg", fmt(row.get("volume_ratio", 0), ".2f") + "×")

        above_flag = bool(safe_float(row.get("above_ma20", 0)))
        st.markdown("**Technical**")
        st.write("Above MA20:", "Yes" if above_flag else "No")
        st.info(
            "Sync the IDX-API database for a full price chart:\n```\n"
            "cd /Users/edbert/IDX-API && deno run -A sync_for_mantra.ts\n```"
        )


# ── Tab 4: History ────────────────────────────────────────────────────────────
with tab_history:
    hist = cached_ticker_history(selected_ticker, CONFIG_PATH)
    if hist.empty:
        st.info("No score history yet — run the screener on multiple days to build history.")
    else:
        hist = hist.sort_values("date").copy()
        hist["date"] = pd.to_datetime(hist["date"].astype(str))

        score_vars = [c for c in ["investment_score", "broker_flow_real_score"] if c in hist.columns]
        melted = hist.melt(
            "date",
            value_vars=score_vars,
            var_name="Metric",
            value_name="Score",
        )
        melted["Metric"] = melted["Metric"].map({
            "investment_score":       "Investment",
            "broker_flow_real_score": "BF Real",
        })

        score_chart = (
            alt.Chart(melted)
            .mark_line(strokeWidth=2)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("Score:Q", scale=alt.Scale(domain=[0, 100]), title="Score"),
                color=alt.Color(
                    "Metric:N",
                    scale=alt.Scale(
                        domain=["Investment", "BF Real"],
                        range=[ALTAIR_GREEN, ALTAIR_AMBER],
                    ),
                ),
                tooltip=["date:T", "Metric:N", alt.Tooltip("Score:Q", format=".1f")],
            )
            .properties(height=260, title=f"{selected_ticker} — Score History")
        )
        st.altair_chart(score_chart, width="stretch")

        # Action history table
        hist_cols = [c for c in ["date", "action", "investment_score", "broker_flow_real_score", "breakout_signal"] if c in hist.columns]
        hist_disp = hist[hist_cols].copy()
        hist_disp["date"] = hist_disp["date"].dt.strftime("%Y-%m-%d")
        hist_disp = hist_disp.sort_values("date", ascending=False)

        def _col_action(v: str) -> str:
            c = ACTION_COLORS.get(str(v), "#78909C")
            return f"color: {c}; font-weight: bold"

        fmt_hist = {c: "{:.1f}" for c in ["investment_score", "broker_flow_real_score"] if c in hist_disp.columns}
        st.dataframe(
            hist_disp.style
            .map(_col_action, subset=["action"])
            .format(fmt_hist, na_rep="—"),
            hide_index=True,
            width="stretch",
        )
