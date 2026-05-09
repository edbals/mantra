"""
MyMantra — About / Methodology page
Long-form explainer rendered as a single Streamlit markdown column.
Content sourced from mantra_final.md (Parts A, C, and the technical Appendix).
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="MyMantra | About",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Light styling — keeps the dark theme from Dashboard.py while widening
# the reading column and tightening typography for long-form copy.
st.markdown(
    """
    <style>
      .block-container {
        max-width: 880px !important;
        padding-top: 56px !important;
        padding-bottom: 96px !important;
      }
      .about-eyebrow {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #8A8B95;
        font-weight: 500;
        margin: 0 0 14px 0;
      }
      .about-hero {
        font-size: 48px;
        line-height: 1.05;
        letter-spacing: -0.035em;
        font-weight: 700;
        color: #E8ECF0;
        margin: 0 0 12px 0;
      }
      .about-sub {
        font-size: 17px;
        line-height: 1.7;
        color: #B8BBC4;
        margin: 0 0 56px 0;
        max-width: 640px;
      }
      h2 {
        font-size: 28px !important;
        letter-spacing: -0.02em !important;
        margin-top: 64px !important;
        margin-bottom: 8px !important;
      }
      h3 {
        font-size: 18px !important;
        letter-spacing: -0.01em !important;
        margin-top: 32px !important;
        margin-bottom: 6px !important;
      }
      .about-body p, .about-body li {
        font-size: 16px;
        line-height: 1.7;
        color: #C5C7CD;
      }
      .about-body strong { color: #E8ECF0; }
      .about-body table { width: 100%; border-collapse: collapse; margin: 18px 0; }
      .about-body th, .about-body td {
        text-align: left; padding: 10px 12px;
        border-bottom: 1px solid #2D3140;
        font-size: 14px;
      }
      .about-body th {
        text-transform: uppercase; letter-spacing: 0.08em;
        font-size: 11px; font-weight: 500; color: #8A8B95;
      }
      .pill {
        display: inline-block; padding: 2px 10px; border-radius: 99px;
        font-size: 12px; font-weight: 600; letter-spacing: 0.02em;
        margin-right: 6px;
      }
      .pill-invest    { background:#00C85322; color:#00C853; border:1px solid #00C853; }
      .pill-watchex   { background:#D4E60022; color:#D4E600; border:1px solid #D4E600; }
      .pill-watch     { background:#FFB30022; color:#FFB300; border:1px solid #FFB300; }
      .pill-observe   { background:#FF6D0022; color:#FF6D00; border:1px solid #FF6D00; }
      .pill-avoid     { background:#FF174422; color:#FF1744; border:1px solid #FF1744; }
      .pill-illiquid  { background:#78909C22; color:#78909C; border:1px solid #78909C; }
      .cta-row { margin: 56px 0 8px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <p class="about-eyebrow">IDX Stock Screener</p>
    <h1 class="about-hero">Find where institutions<br>are quietly buying.</h1>
    <p class="about-sub">
      Mantra scans all 870 IDX stocks daily, reads broker transaction flow,
      and identifies where institutional capital is accumulating — before
      price confirms the move.
    </p>
    """,
    unsafe_allow_html=True,
)

if st.button("Open the screener", type="primary"):
    st.switch_page("Dashboard.py")

st.divider()


# ── Long-form body ────────────────────────────────────────────────────────────
st.markdown('<div class="about-body">', unsafe_allow_html=True)


# Section 1 — The data advantage
st.markdown(
    """
## A structural property most markets don't have

Every equity transaction on the Indonesian Stock Exchange is publicly
attributed to a specific broker code at the end of each trading day.
In markets like the US or Europe, this simply doesn't exist.
Institutional order flow there is deliberately hidden, routed through
dark pools, fragmented across alternative trading systems, or disguised
via payment-for-order-flow agreements between retail brokerages and
wholesale market makers.

The standard academic approach to measuring institutional presence in
those markets is inferential. Researchers use models like PIN
(Probability of Informed Trading) or VPIN (Volume-Synchronized
Probability of Informed Trading) to estimate who is buying based on
trade imbalances and quote dynamics, because the actual broker identity
is never disclosed. On the IDX, it is. The attribution data allows
direct empirical observation of informed order flow, not inference
from it.
"""
)


# Section 2 — What we measure
st.markdown(
    """
## Not all volume is equal. Not even close.

A stock that trades heavily on a given day might be in the early stages
of something significant, or it might be completely routine. Volume
alone doesn't distinguish between the two.

What matters is **behavioral divergence**. Academic research on retail
investor habitats consistently documents retail flow as a contrarian
indicator, with retail participants tending to supply liquidity at
precisely the points when informed capital is absorbing it. When that
absorption is sustained across multiple sessions and concentrated among
a small number of broker codes rather than fragmented across thousands
of accounts, it produces the kind of supply contraction that Wurgler
and Zhuravskaya (2002) identified as a precursor to exaggerated price
responses, particularly in environments where the available float is
constrained.

Mantra quantifies that pattern. The score reflects its strength.
"""
)


# Section 3 — What Mantra is
st.markdown(
    """
## A starting point. Not a conclusion.

Mantra narrows 870 stocks to a short list worth investigating. That is
the entire job. It does not recommend positions, manage risk, or tell
you when to exit. The label **INVEST** means the data is aligned in a
pattern that has historically preceded sustained price discovery on
the IDX. **It does not mean buy.**

The due diligence on the company behind the ticker — its fundamentals,
its capital structure, and its risk profile — is research you have to
do yourself. Mantra shows you where to look. What you find when you
look is your responsibility.

Past signals do not guarantee future performance.
"""
)


# Section 4 — The numbers
st.markdown(
    """
## The numbers
"""
)
n1, n2, n3 = st.columns(3)
with n1:
    st.markdown(
        "<div style='font-size:56px;font-weight:700;color:#E8ECF0;"
        "letter-spacing:-0.04em;line-height:1;font-variant-numeric:tabular-nums'>870</div>"
        "<div style='color:#8A8B95;font-size:13px;margin-top:8px'>"
        "IDX equities evaluated nightly</div>",
        unsafe_allow_html=True,
    )
with n2:
    st.markdown(
        "<div style='font-size:56px;font-weight:700;color:#E8ECF0;"
        "letter-spacing:-0.04em;line-height:1;font-variant-numeric:tabular-nums'>100</div>"
        "<div style='color:#8A8B95;font-size:13px;margin-top:8px'>"
        "candidates selected for deep, per-broker statistical analysis</div>",
        unsafe_allow_html=True,
    )
with n3:
    st.markdown(
        "<div style='font-size:56px;font-weight:700;color:#E8ECF0;"
        "letter-spacing:-0.04em;line-height:1;font-variant-numeric:tabular-nums'>2</div>"
        "<div style='color:#8A8B95;font-size:13px;margin-top:8px'>"
        "independent validation methods required to agree</div>",
        unsafe_allow_html=True,
    )

st.markdown(
    """
The 100 candidates for deep analysis are not selected by raw score.
They are ranked by a function that specifically targets the
microstructural environment where order flow has the greatest price
impact: stocks where float pressure is high relative to liquidity.
That is where informed accumulation fractures the order book fastest.
"""
)


# Section 5 — The methodology
st.markdown(
    """
## Built on published market microstructure research

### Stage 1 — Four signals, every stock

Every score starts here. Four signals, combined into a single score
from 0 to 100.

| Signal | Weight | What it measures |
|---|---|---|
| **Broker flow conviction** | 40% | Who is transacting, and does their behavior represent a statistically meaningful deviation from their own history. |
| **Free-float pressure** | 30% | How fast the tradable supply of shares is tightening. Draws on Wurgler & Zhuravskaya (2002) — constrained float yields exaggerated price responses to demand shocks. |
| **Liquidity depth** | 20% | Informed by Amihud's classical illiquidity measures. Any stock with a 20-day average daily traded value below IDR 500 million is excluded immediately. |
| **Price structure** | 10% | Proximity to 20-day highs, volume confirmation, and volatility contraction relative to moving-average baselines. |

### Stage 2 — Two independent validation methods, top 100 only

The 100 candidates selected from Stage 1 are then validated by two
methods that **must both confirm** before a stock reaches the list.

**Z-score analysis.** Each broker's daily net volume is measured
against their own 60-day historical baseline. A Z-score of 1.5 or
above places the broker's activity above the 93rd percentile of their
own prior sessions. The application of Z-score methodology to trading
volume anomaly detection follows the approach that quantitative finance
adapted from Altman's foundational 1968 work on statistical deviation.

**Isolation Forest** (Liu, Ting, and Zhou, 2008). A non-parametric
machine-learning algorithm that does not assume trading volume follows
a normal distribution. That matters because IDX volume data exhibits
right-tail skewness and heteroskedasticity that makes parametric
assumptions unreliable. Isolation Forest detects anomalies that a
Z-score would miss entirely — specifically subtle shifts in directional
behavior that occur without a change in volume.

Both methods must flag the same broker on the same day.
**One confirmation is not enough.**
"""
)


# Section 6 — Decision labels
st.markdown(
    """
## Decision labels

Every stock receives a score from 0 to 100 each day, built from four
signals: order flow conviction (40%), free-float pressure (30%),
liquidity depth (20%), and price structure (10%). A score of 55 or
above indicates a meaningful accumulation signal. Below 35 suggests the
opposite. The label is determined by the score and by whether price
has begun to confirm the move.
"""
)

st.markdown(
    """
<span class="pill pill-invest">INVEST</span>
**Score 55 or above. Breakout confirmed.** Accumulation is present and
price is beginning to confirm it on volume. Highest priority for
immediate research.

<span class="pill pill-watchex">WATCH&nbsp;EXEC</span>
**Score 55 or above. No breakout yet.** The signal is clearly there.
Price has not confirmed the move. This is the setup. Enter when it does.

<span class="pill pill-watch">WATCH</span>
**Score 45 to 54.** Something is building. Not there yet. Worth
checking daily.

<span class="pill pill-observe">OBSERVE</span>
**Score 35 to 44.** A signal is forming but lacks directional
conviction. Passive monitoring only.

<span class="pill pill-avoid">AVOID</span>
**Score below 35, or OJK suspended.** Flow dynamics are unfavourable
or regulatory risk is present.

<span class="pill pill-illiquid">ILLIQUID</span>
**Average daily traded value below IDR 500M.** Cannot be traded in
meaningful size. Excluded from all scoring.
""",
    unsafe_allow_html=True,
)


# Broker anomaly note
st.markdown(
    """
### Broker anomaly score

A secondary signal that measures whether specific broker activity is
statistically unusual relative to that broker's own history. It
supplements the investment score; it does not replace it.

| Score | What it means |
|---|---|
| 70 or above | Highly anomalous. Pay attention. |
| 50–70 | Moderate deviation. Worth noting alongside the label. |
| Below 50 | Normal operating range. |

An **INVEST** label paired with an anomaly score of 70 or above is the
highest-conviction output the system generates. The two signals are
produced by independent methods and are confirming each other.
"""
)


# Section 7 — Limitations
st.markdown(
    """
## Straight talk on limitations

1. **End-of-day data only.** Intra-day moves, flash crashes, and live
   order flow are invisible. Signals are for the next session's open.
   If you need intra-day execution intelligence, this is not that tool.

2. **Heuristic weights, not machine-optimised.** The factor weights —
   40% broker flow, 30% float pressure, 20% liquidity, 10% price
   structure — were manually calibrated against Indonesian market
   behaviour. They represent a structured hypothesis, not the output
   of gradient descent against a held-out test set. They will be wrong
   in cases outside that hypothesis.

3. **High conviction is not low risk.** Low-float stocks score well
   when accumulation is concentrated. They collapse fast when it stops.
   Those two facts coexist. A high score reflects signal strength, not
   downside safety.

4. **Z-score requires history to be valid.** A minimum of 20 days of
   broker trading history is required before Z-score analysis can be
   applied. Brokers activating after dormancy or IPOs with thin history
   are excluded until the baseline is established. A sample below 20
   produces unstable variance and generates false positives. The
   exclusion is intentional.

5. **Disguised accumulation.** If an entity fragments accumulation
   across many retail proxy accounts to avoid detection, the model will
   temporarily misclassify the flow until behavioral patterns
   recalibrate. This is a structural limitation of any
   broker-attribution approach, not specific to Mantra.

This is for research. Do your own work.
"""
)


# Section 8 — Technical notes
st.markdown(
    """
## Technical notes

**Presence boosts.** When a specific type of institutional broker
crosses the Z-score threshold, the stock receives an additive boost:

| Broker type | Boost |
|---|---|
| Market maker | +12 |
| Issuer-affiliated | +10 |
| Institutional capital | +8 |
| Arbitrage / crossing | +6 |

Maximum total boost per stock is capped at +30.

**The float amplifier.** Accumulation in a tight-float stock has
exponentially more price impact than the same order in a high-float
name. Mantra applies a logarithmic amplifier that mathematically
rewards this environment. The academic basis is well established in
market microstructure literature.

**Data sources.** End-of-day broker transaction data from the
Indonesian Stock Exchange via the Index Alpha API. Data is processed
nightly. Signals are available by market open the following trading
day.

---

*Mantra is a quantitative research instrument intended for idea
generation and portfolio research. It does not constitute financial
advice. Independent due diligence is required. Historical signals do
not guarantee future performance.*
"""
)

st.markdown("</div>", unsafe_allow_html=True)


# CTA
st.markdown('<div class="cta-row">', unsafe_allow_html=True)
if st.button("Open the screener", type="primary", key="cta_bottom"):
    st.switch_page("Dashboard.py")
st.markdown("</div>", unsafe_allow_html=True)
