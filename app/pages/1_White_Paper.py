"""
MyMantra — Strategy White Paper
Accessible at: streamlit run app/dashboard.py → White Paper page
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(
    page_title="White Paper — MyMantra",
    page_icon="📄",
    layout="wide",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Poppins', sans-serif !important; }
  .wp-section {
    background: #1A1D27;
    border-radius: 10px;
    padding: 24px 32px;
    margin-bottom: 24px;
  }
  .formula-box {
    background: #0D1117;
    border-left: 3px solid #00C853;
    border-radius: 6px;
    padding: 14px 20px;
    font-family: monospace;
    font-size: 0.92rem;
    margin: 12px 0;
    color: #E8E8E8;
  }
  .note-box {
    background: #1A2A1A;
    border-left: 3px solid #FFB300;
    border-radius: 6px;
    padding: 12px 18px;
    margin: 12px 0;
    font-size: 0.88rem;
    color: #DDD;
  }
</style>
""", unsafe_allow_html=True)

st.markdown("# MyMantra — Strategy White Paper")
st.caption("Version 2.2 · Experimental · For the Indonesian Stock Exchange (IDX)")
st.divider()


# ── Abstract ──────────────────────────────────────────────────────────────────
st.markdown("## Abstract")
st.markdown("""
MyMantra is a quantitative stock screener for the Indonesian Stock Exchange (IDX) that ranks
equities by the probability of institutional accumulation, as inferred from broker transaction
flow, free-float pressure, price structure, and liquidity.

The system operates in two stages. **Stage 1** scores all listed tickers using proxy signals
derived from the local IDX transaction database — cheap, fast, no external API calls.
**Stage 2** selects the top 100 candidates and re-scores them using real, per-broker
transaction data from the Index Alpha API, applying z-score analysis to identify brokers
buying significantly above their own historical baseline.

The output is a ranked watchlist with six decision labels:
**INVEST · WATCH_EXEC · WATCH · OBSERVE · AVOID · ILLIQUID**.

> ⚠️ This tool is experimental and designed for research purposes. It is not financial advice.
> Past screening signals do not guarantee future returns.
""")

st.divider()


# ── Why Broker Flow ───────────────────────────────────────────────────────────
st.markdown("## 1 · Why Broker Flow?")
st.markdown("""
In Indonesia, every equity transaction is publicly attributed to a broker code.
This means it is possible to observe, in near real-time, whether institutional brokers
are accumulating or distributing a stock — information that is typically hidden in
markets where order-flow data is proprietary.

The IDX broker data reveals three structurally important signals:

| Signal | Logic |
|---|---|
| **Institutional net buying** | Institutional and market-maker brokers buying above their own historical average suggests informed accumulation |
| **Retail net selling** | When retail brokers (e.g. Stockbit, Ajaib) are net sellers, it removes the supply overhang — institutions can absorb quietly |
| **Absorption ratio** | If institutions absorb more than retail sells, the float tightens — price impact of any subsequent buying increases |

Two brokers are structurally important:

- **XL (Stockbit)** and **XC (Ajaib)** are the two largest retail-facing platforms by account count.
  When XL/XC are net sellers, retail participation is exiting — historically a bullish divergence
  signal when institutional brokers simultaneously absorb that selling.
  When XL/XC are net buyers, retail is piling in — typically a sign that institutions are
  distributing into retail demand.
""")

st.divider()


# ── Stage 1 ───────────────────────────────────────────────────────────────────
st.markdown("## 2 · Stage 1 — Proxy Scoring (All ~870 Tickers)")
st.markdown("""
Stage 1 runs entirely against the local IDX-API SQLite database.
It computes five feature scores (each 0–100), then combines them into an Investment Score.
""")

st.markdown("### 2.1 · Feature Scores")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Broker Flow (Proxy) — weight ×0.40")
    st.markdown("""
    Built from the aggregate buy/sell volumes across broker classes, classified into:
    - **Institutional** (large securities firms)
    - **Market Maker**
    - **Emitent** (issuer-affiliated)
    - **Zombie** (crossing/arbitrage brokers)
    - **Retail** (retail_pure, retail_mixed)

    Four sub-signals, equally normalised to [0, 1]:
    """)
    st.markdown("""
    <div class="formula-box">
    retail_sell_share  × 30<br>
    + absorption_ratio_norm × 25<br>
    + accum_streak_norm    × 25<br>
    + fragmentation_norm   × 20<br>
    = broker_flow_score (0–100)
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Float Pressure — weight ×0.30")
    st.markdown("""
    Measures how much of the free float is being actively traded and accumulated.
    A tight float amplifies price impact — the same institutional buying moves a LOW-float
    stock far more than a HIGH-float one.
    """)
    st.markdown("""
    <div class="formula-box">
    turnover_to_float_norm × 35<br>
    + accum_to_float_norm  × 40<br>
    + float_tightness      × 25<br>
    = float_pressure_score (0–100)
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("#### Liquidity — weight ×0.20")
    st.markdown("""
    Filters out stocks that cannot be traded meaningfully.
    Based on 20-day average daily traded value (IDR) and the spread proxy
    (daily high−low range as % of close).

    Stocks averaging < IDR 500M/day are labeled **ILLIQUID** regardless of score.
    """)

    st.markdown("#### Structure — weight ×0.10")
    st.markdown("""
    Price and volume structure relative to the IHSG index:
    - Position relative to MA20 and MA50
    - 20-day range compression (coiling)
    - Volume ratio (today vs 20-day average)
    - Relative strength vs IHSG
    """)

    st.markdown("#### Catalyst (Informational only) — weight ×0.00")
    st.markdown("""
    Forward-looking corporate events within defined windows:
    - Dividend ex-date within 30 days
    - Rights offering within 60 days
    - Stock split within 30 days
    - Material announcements within 7 days

    **Catalyst does not enter the investment score** — it is displayed as context only.
    Suspension by OJK triggers a hard **AVOID** override regardless of score.
    """)

st.markdown("### 2.2 · Stage 1 Investment Score")
st.markdown("""
<div class="formula-box">
investment_score =<br>
&nbsp;&nbsp;broker_flow_score    × 0.40<br>
&nbsp;&nbsp;+ float_pressure_score × 0.30<br>
&nbsp;&nbsp;+ structure_score      × 0.10<br>
&nbsp;&nbsp;+ liquidity_score      × 0.20<br>
<br>
Clamped to [0, 100]
</div>
""", unsafe_allow_html=True)

st.divider()


# ── Stage 2 ───────────────────────────────────────────────────────────────────
st.markdown("## 3 · Stage 2 — Real Broker Flow (Top 100)")

st.markdown("### 3.1 · Candidate Selection")
st.markdown("""
The top 100 tickers for Stage 2 are selected from the Stage 1 pool by a rank key
that favours **high float pressure** combined with **lower liquidity** — the names
where broker flow has the greatest price impact per unit of volume:
""")
st.markdown("""
<div class="formula-box">
stage1_rank_key =<br>
&nbsp;&nbsp;float_pressure_score × 0.6<br>
&nbsp;&nbsp;+ (100 − liquidity_score) × 0.4<br>
<br>
ILLIQUID tickers are excluded before selection.
</div>
""", unsafe_allow_html=True)

st.markdown("### 3.2 · Z-Score Sustained Buyers")
st.markdown("""
For each of the 100 selected tickers, the Index Alpha API provides per-broker,
per-day transaction volumes going back 60 trading days (~3 months).

For every **institutional, Market Maker, Emitent, or Zombie** broker active today,
MyMantra computes a z-score against that broker's own historical baseline:
""")
st.markdown("""
<div class="formula-box">
z = (net_volume_today − μ_historical) / σ_historical<br>
<br>
Flagged as "buying above average" when z ≥ 1.5<br>
Minimum 20 days of history required (σ stable within ~30% error at n=20)
</div>
""", unsafe_allow_html=True)
st.markdown("""
Brokers with z ≥ 1.5 receive a **Presence Boost** added to the score:

| Broker class | Boost |
|---|---|
| Market Maker | +12 |
| Emitent (issuer-affiliated) | +10 |
| Institutional | +8 |
| Zombie | +6 |
| **Maximum total boost** | **+30** |
""")

st.markdown("### 3.3 · Real Broker Flow Score")
st.markdown("""
The real broker flow score replaces the proxy for Stage 2 tickers:
""")
st.markdown("""
<div class="formula-box">
base_score =<br>
&nbsp;&nbsp;retail_sell_norm  × 30  &nbsp;# retail net selling as % of total vol (cap 30%)<br>
&nbsp;&nbsp;+ absorption_norm × 25  &nbsp;# inst net buy / retail net sell (cap 2:1 ratio)<br>
&nbsp;&nbsp;+ accum_norm      × 25  &nbsp;# inst net buy as % of float (cap 5% of float/day)<br>
&nbsp;&nbsp;+ streak_norm     × 20  &nbsp;# consecutive days inst were net buyers (cap 10d)<br>
<br>
final_score = clip(base_score + presence_boost ± xl_xc_adj, 0, 100)<br>
<br>
XL/XC net selling today → +15 (retail exiting, bullish)<br>
XL/XC net buying today  → −15 (retail piling in, bearish)
</div>
""", unsafe_allow_html=True)

st.divider()


# ── Interaction term ──────────────────────────────────────────────────────────
st.markdown("## 4 · Interaction Term — Float Amplifier")
st.markdown("""
Inspired by Wurgler & Zhuravskaya (2002), who showed that stocks with fewer arbitrage
substitutes (i.e. tight floats) experience larger price reactions to demand shocks,
MyMantra applies a **float amplifier** to the broker flow signal.

The intuition: a broker buying 1M lots of a LOW-float stock moves the price far more
than the same 1M lots of a HIGH-float stock. The signal is stronger where the float
is tightest.
""")
st.markdown("""
<div class="formula-box">
float_amplifier = clip( log(1 / free_float_pct) / log(20), 0, 1 )<br>
<br>
Examples:<br>
&nbsp;&nbsp;5% free float  → amplifier ≈ 1.00  (maximum)<br>
&nbsp;&nbsp;20% free float → amplifier ≈ 0.53<br>
&nbsp;&nbsp;50% free float → amplifier ≈ 0.23<br>
<br>
interaction_bonus = 7.0 × float_amplifier × (broker_flow_real_score / 100)<br>
Maximum bonus: +7 pts (additive — does not alter weight constraints)
</div>
""", unsafe_allow_html=True)

st.markdown("### XL/XC Trend Boost")
st.markdown("""
If XL/XC have been net sellers for 3 or more of the last 10 trading days (sustained
retail exit rather than a single-day blip), an additional trend boost is applied,
scaled by float category and trend intensity:
""")
st.markdown("""
<div class="formula-box">
trend_boost = ff_max × (xl_xc_trend_days / 10)<br>
<br>
ff_max: LOW float → +5 pts, MID → +3 pts, HIGH → +1 pt<br>
xl_xc_trend_days / 10: scales linearly — 3 days = 30%, 10 days = 100%
</div>
""", unsafe_allow_html=True)

st.markdown("### Final Stage 2 Investment Score")
st.markdown("""
<div class="formula-box">
investment_score (Stage 2) =<br>
&nbsp;&nbsp;broker_flow_real_score    × 0.40<br>
&nbsp;&nbsp;+ float_pressure_score    × 0.30<br>
&nbsp;&nbsp;+ structure_score         × 0.10<br>
&nbsp;&nbsp;+ liquidity_score         × 0.20<br>
&nbsp;&nbsp;+ interaction_bonus       (up to +7)<br>
&nbsp;&nbsp;+ trend_boost             (up to +5 / +3 / +1)<br>
<br>
Clamped to [0, 100]
</div>
""", unsafe_allow_html=True)

st.divider()


# ── Decision labels ───────────────────────────────────────────────────────────
st.markdown("## 5 · Decision Labels")
st.markdown("""
Every scored ticker receives exactly one label. They are applied in strict priority order:
""")

labels = [
    ("🔴 ILLIQUID",    "#78909C", "Average daily traded value < IDR 500M. Cannot be traded in meaningful size. Excluded from all other logic."),
    ("🔴 AVOID",       "#FF1744", "Suspended by OJK (hard override), OR investment score < 35."),
    ("🟠 OBSERVE",     "#FF6D00", "Investment score 35–44. On the radar but no actionable signal yet."),
    ("🟡 WATCH",       "#FFB300", "Investment score 45–54. Accumulation building — monitor closely."),
    ("🟡 WATCH_EXEC",  "#D4E600", "Investment score ≥ 55 but NO breakout signal. Strong fundamentals, waiting for price confirmation."),
    ("🟢 INVEST",      "#00C853", "Investment score ≥ 55 AND breakout signal active. Both accumulation signal and price confirmation present."),
]

for label, color, desc in labels:
    st.markdown(
        f"<div style='display:flex;align-items:flex-start;gap:16px;padding:10px 0;"
        f"border-bottom:1px solid #2D3140'>"
        f"<b style='color:{color};min-width:120px;font-size:0.9rem'>{label}</b>"
        f"<span style='color:#CCC;font-size:0.88rem'>{desc}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("")
st.markdown("""
<div class="note-box">
<b>Breakout signal</b> is True when: close ≥ 98% of the 20-day rolling high AND
today's volume is at least 1.2× the 20-day average. This identifies stocks that are
near a price breakout with above-average participation — not just accumulating quietly,
but beginning to move.
</div>
""", unsafe_allow_html=True)

st.divider()


# ── Anomaly detection ─────────────────────────────────────────────────────────
st.markdown("## 6 · Broker Anomaly Detection")
st.markdown("""
The Broker Analysis tab includes an **Isolation Forest** model trained per-broker
on historical net volume. This is a complementary signal to the z-score.

**Z-score** assumes broker net volume is approximately normally distributed and
measures deviation in standard-deviation units. It is simple, fast, and interpretable.

**Isolation Forest** makes no distributional assumption. It identifies observations
that are easy to isolate from the rest of the data — i.e. they sit in sparse regions
of the feature space. It uses five features per (broker, day):
- Net volume, Buy volume, Sell volume
- Buy ratio (buys / total), Net ratio (net / total)

Both methods are fitted **only on historical data** — the signal period (today or
recent days) is never included in training, avoiding lookahead bias.

Anomaly scores are normalised to [0, 100]:
- **≥ 70**: highly anomalous activity — investigate
- **50–70**: moderately unusual
- **< 50**: within normal range
""")

st.divider()


# ── Limitations ───────────────────────────────────────────────────────────────
st.markdown("## 7 · Limitations & Known Risks")

st.markdown("""
| Risk | Detail |
|---|---|
| **Survivorship bias** | Only currently listed tickers are scored. Delisted stocks are not included in any back-test. |
| **Look-ahead in development** | The scoring weights were chosen by the developer with knowledge of general IDX market behaviour — they have not been optimised on a held-out test set. |
| **Small float ≠ safe** | LOW-float stocks score higher due to the float amplifier, but they also carry higher liquidity risk and are more susceptible to manipulation. |
| **Z-score instability** | Brokers with fewer than 20 days of history are excluded from z-score computation. New tickers or infrequently-traded brokers may have unreliable baselines. |
| **API data lag** | Index Alpha data is fetched as of market close. Intra-day signals are not captured. |
| **Single-factor risk** | The model is dominated by broker flow (×0.40 weight). A broker reclassification or change in trading behaviour can significantly affect scores. |
| **No position sizing** | MyMantra ranks stocks but does not compute optimal position sizes, stop-losses, or portfolio-level risk. |
""")

st.markdown("""
<div class="note-box">
This screener is a research instrument. It is designed to surface candidates for
further analysis — not to generate buy or sell signals autonomously.
Always conduct your own due diligence before making any investment decision.
</div>
""", unsafe_allow_html=True)

st.divider()


# ── References ────────────────────────────────────────────────────────────────
st.markdown("## 8 · References")
st.markdown("""
- Wurgler, J. & Zhuravskaya, E. (2002). *Does arbitrage flatten demand curves for stocks?*
  Journal of Business, 75(4), 583–608. *(Basis for the float amplifier interaction term)*
- Amihud, Y. (2002). *Illiquidity and stock returns: cross-section and time-series effects.*
  Journal of Financial Markets, 5(1), 31–56. *(Basis for liquidity scoring)*
- Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). *Isolation Forest.*
  IEEE International Conference on Data Mining. *(Anomaly detection model)*
- IDX (Indonesia Stock Exchange) — broker transaction data via IDX-API
- Index Alpha (indexalpha.id) — per-broker daily transaction API
""")

st.caption("MyMantra v2.2 · Built with Streamlit · Strategy designed for IDX · Not financial advice")
