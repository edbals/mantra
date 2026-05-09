"""
MyMantra Dashboard v2 — Bloomberg-style React prototype embedded in Streamlit.

Currently uses mock data from app/v2/src/data.js. Real data wiring is the
next step — a Python adapter will read scores_*.csv and inject window.IDX_DATA
before serving.

The AI Insights banner IS already wired to live data — see build_ai_insights().
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Dashboard v2 — MyMantra",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Strip Streamlit chrome so the embedded app fills the viewport
st.markdown(
    """
    <style>
      header[data-testid="stHeader"] { display: none; }
      .block-container { padding: 0 !important; max-width: 100% !important; }
      footer { display: none; }
      [data-testid="stSidebarCollapsedControl"] { display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

V2_DIR     = Path(__file__).parent.parent / "v2"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


def build_ai_insights() -> str:
    """
    Compose the AI Insights banner from the latest scored CSV. Pure data lookup
    — no LLM. Output is a small HTML snippet ready to inject as window.AI_INSIGHTS.
    """
    csv_files = sorted(glob.glob(str(OUTPUT_DIR / "scores_*.csv")))
    if not csv_files:
        return ""
    df = pd.read_csv(csv_files[-1])

    # Stage-2 only — the metrics below only make sense with real broker flow
    if "broker_data_source" in df.columns:
        df = df[df["broker_data_source"] == "indexalpha"].copy()
    if df.empty:
        return ""

    # Institutional absorption: ratio > 1.5 AND solid broker-flow score
    if "absorption_ratio" in df.columns and "broker_flow_real_score" in df.columns:
        absorbing = (
            df[(df["absorption_ratio"] > 1.5) & (df["broker_flow_real_score"] >= 60)]
            .sort_values("broker_flow_real_score", ascending=False)
            .head(3)
        )
    else:
        absorbing = pd.DataFrame()

    # Sustained retail exit (XL/XC/YP net selling 3+ of last 10 days)
    n_retail_exit = (
        int(df["xl_xc_trend_selling"].fillna(False).astype(bool).sum())
        if "xl_xc_trend_selling" in df.columns else 0
    )

    # Institutional accumulation streak ≥ 3 days
    n_streak = (
        int((df["accum_streak"].fillna(0) >= 3).sum())
        if "accum_streak" in df.columns else 0
    )

    # INVEST signals (breakout + score ≥ 55)
    n_invest = int((df.get("action", pd.Series(dtype=str)) == "INVEST").sum())

    parts = []

    if n_invest > 0:
        parts.append(f"<b>{n_invest} INVEST signal{'s' if n_invest != 1 else ''}</b> active today.")

    if not absorbing.empty:
        tickers = ", ".join(f"<b>{t}</b>" for t in absorbing["ticker"].tolist())
        parts.append(f"Institutional absorption (&gt;1.5×) detected in {tickers}.")

    if n_retail_exit > 0:
        parts.append(
            f"<b>Sustained retail exit</b> (Stockbit / Ajaib / Mirae) confirmed in "
            f"{n_retail_exit} ticker{'s' if n_retail_exit != 1 else ''}."
        )

    if n_streak > 0:
        parts.append(f"{n_streak} tickers with 3+ day institutional accumulation streak.")

    if not parts:
        return "No notable broker-flow signals today across the Stage 2 universe."

    return " ".join(parts)


def build_inlined_html() -> str:
    """Read index.html and inline every local CSS/JS file referenced by it."""
    html = (V2_DIR / "index.html").read_text()

    css = (V2_DIR / "src" / "styles.css").read_text()
    html = html.replace(
        '<link rel="stylesheet" href="src/styles.css"/>',
        f"<style>{css}</style>",
    )

    data_js = (V2_DIR / "src" / "data.js").read_text()
    html = html.replace(
        '<script src="src/data.js"></script>',
        f"<script>{data_js}</script>",
    )

    for jsx in ("icons", "ui", "charts", "views", "app"):
        content = (V2_DIR / "src" / f"{jsx}.jsx").read_text()
        html = html.replace(
            f'<script type="text/babel" data-presets="react" src="src/{jsx}.jsx"></script>',
            f'<script type="text/babel" data-presets="react">{content}</script>',
        )

    # Inject live AI insights banner BEFORE the React scripts run.
    insights_js = f"<script>window.AI_INSIGHTS = {json.dumps(build_ai_insights())};</script>"
    html = html.replace("<script src=\"https://unpkg.com/react@", insights_js + "\n  <script src=\"https://unpkg.com/react@", 1)

    return html


components.html(build_inlined_html(), height=1100, scrolling=True)
