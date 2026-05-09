"""
Mantra Dashboard v2 — Bloomberg-style React prototype embedded in Streamlit.

Currently uses mock data from app/v2/src/data.js. Real data wiring is the
next step — a Python adapter will read scores_*.csv and inject window.IDX_DATA
before serving.

The AI Insights banner IS already wired to live data — see build_ai_insights().
"""
from __future__ import annotations

import glob
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

_LOGO = Path(__file__).parent.parent / "v2" / "logo.png"

st.set_page_config(
    page_title="Dashboard v2 — Mantra",
    page_icon=str(_LOGO) if _LOGO.exists() else "📊",
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


def _xlxc_state(row) -> str:
    """Map a scored row's xl/xc booleans to the prototype's enum."""
    if row.get("xl_xc_selling"):
        return "net-sell"
    if row.get("xl_xc_buying"):
        return "net-buy"
    return "balance"


def _anomaly_proxy(row) -> int:
    """
    The prototype expects a 0–100 anomaly score per ticker. We don't store
    one in the CSV, so synthesise from existing signals:
      score_adj  ∈ ~[-15, 30]  →  scaled to ~[0, 90]
      accum_streak ∈ [0, 10]   →  +0–10 bonus when above 3
    """
    adj_raw = row.get("score_adj")
    adj = 0.0 if pd.isna(adj_raw) else float(adj_raw or 0)
    streak_raw = row.get("accum_streak")
    streak = 0.0 if pd.isna(streak_raw) else float(streak_raw or 0)
    base = max(0.0, adj) * 3.0
    streak_bonus = max(0.0, min(10.0, streak - 3) * 2.0)
    return int(min(100, base + streak_bonus + abs(min(0.0, adj)) * 1.5))


def _f(v, default=0.0) -> float:
    """Float-or-default that handles NaN, None, and empty strings."""
    try:
        f = float(v)
        return default if pd.isna(f) else f
    except (TypeError, ValueError):
        return default


def list_scored_dates() -> list[str]:
    """Sorted (newest first) list of dates with a scores CSV."""
    csvs = glob.glob(str(OUTPUT_DIR / "scores_*.csv"))
    return sorted([Path(c).stem.replace("scores_", "") for c in csvs], reverse=True)


def pick_csv(date: str | None) -> Path | None:
    """Return the CSV path for `date` if it exists, else the latest."""
    if date:
        candidate = OUTPUT_DIR / f"scores_{date}.csv"
        if candidate.exists():
            return candidate
    csvs = sorted(glob.glob(str(OUTPUT_DIR / "scores_*.csv")))
    return Path(csvs[-1]) if csvs else None


def build_rankings(csv_path: Path | None = None) -> list[dict]:
    """Build the RANKINGS array from a scores CSV (Stage 2 only)."""
    if csv_path is None:
        csv_path = pick_csv(None)
    if csv_path is None or not csv_path.exists():
        return []
    df = pd.read_csv(csv_path)

    if "broker_data_source" in df.columns:
        df = df[df["broker_data_source"] == "indexalpha"].copy()
    if "action" in df.columns:
        df = df[df["action"] != "ILLIQUID"].copy()
    if df.empty:
        return []

    df = df.sort_values("investment_score", ascending=False).reset_index(drop=True)

    rankings = []
    for i, row in df.iterrows():
        name = row.get("company_name")
        if pd.isna(name) or not name:
            name = row["ticker"]
        rankings.append({
            "rank":          int(i + 1),
            "ticker":        str(row["ticker"]),
            "name":          str(name)[:60],
            "action":        str(row.get("action") or "OBSERVE"),
            "score":         round(_f(row.get("investment_score")), 1),
            "breakout":      bool(row.get("breakout_signal")) and not pd.isna(row.get("breakout_signal")),
            "brokerFlow":    round(_f(row.get("broker_flow_real_score")), 1),
            "floatPressure": round(_f(row.get("float_pressure_score")), 1),
            "anomaly":       _anomaly_proxy(row),
            "xlxc":          _xlxc_state(row),
            "close":         int(_f(row.get("close"))),
            "advB":          round(_f(row.get("avg_daily_value_idr")) / 1e9, 1),
            "trend":         0,
        })
    return rankings


def build_anomalies(baseline_days: int = 22) -> tuple[list[dict], list[dict]]:
    """
    Real anomaly detection per watchlist broker, aggregated across all Stage 2
    tickers. Combines:
      - z-score on net volume (today vs baseline mean)
      - Isolation Forest (sklearn) on (net_volume, buy_volume, sell_volume,
        buy_ratio, net_ratio) — fitted on historical baseline only.

    Returns (anomalies, isolation_forest) — both arrays always populated when
    we have enough data; anomalies is the subset that crosses thresholds.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.anomaly import score_brokers

    config_path = Path(__file__).parent.parent.parent / "config.json"
    if not config_path.exists():
        return [], []
    cfg = json.loads(config_path.read_text())
    watchlist = cfg.get("broker_watchlist", [])
    if not watchlist:
        return [], []

    db_path = OUTPUT_DIR / "scores.db"
    if not db_path.exists():
        return [], []

    con = sqlite3.connect(str(db_path))
    placeholders = ",".join("?" * len(watchlist))
    df = pd.read_sql_query(
        f"""
        SELECT date, broker_code AS code,
               SUM(buy_volume)  AS buy_volume,
               SUM(sell_volume) AS sell_volume
        FROM broker_transactions
        WHERE broker_code IN ({placeholders})
        GROUP BY date, broker_code
        ORDER BY date
        """,
        con, params=watchlist,
    )
    con.close()

    # Broker names from broker_master.csv
    try:
        bm = pd.read_csv(Path(__file__).parent.parent.parent / "broker_master.csv")
        col = next((c for c in bm.columns if c.strip().lower() in ("kode perusahaan", "broker_code", "code", "kode")), None)
        ncol = next((c for c in bm.columns if c.strip().lower() in ("nama perusahaan", "name", "broker_name")), None)
        names = dict(zip(bm[col].astype(str).str.strip(), bm[ncol])) if col and ncol else {}
    except Exception:
        names = {}

    if df.empty:
        return [], []

    df["net_volume"] = df["buy_volume"].fillna(0) - df["sell_volume"].fillna(0)

    dates = sorted(df["date"].unique())
    if len(dates) < 5:
        return [], []
    today = dates[-1]
    baseline_dates = dates[-baseline_days-1:-1]

    hist_df   = df[df["date"].isin(baseline_dates)].copy()
    signal_df = df[df["date"] == today].copy()
    if signal_df.empty or hist_df.empty:
        return [], []

    # Real Isolation Forest scores (sklearn, per-broker)
    if_scored = score_brokers(hist_df, signal_df, contamination=0.05)
    if_score_map = dict(zip(if_scored["code"], if_scored["anomaly_score"])) if not if_scored.empty else {}

    # Z-scores on net volume (M lots) for the ANOMALIES table
    anomalies = []
    if_entries = []
    for code in watchlist:
        broker_hist = hist_df[hist_df["code"] == code]["net_volume"]
        if len(broker_hist) < 5:
            continue
        today_net = float(signal_df[signal_df["code"] == code]["net_volume"].sum())
        mu = float(broker_hist.mean())
        sigma = float(broker_hist.std()) or 1.0
        z = (today_net - mu) / sigma

        if_score = float(if_score_map.get(code, 0.0))
        direction = "buy" if today_net > 0 else "sell"
        name = str(names.get(code, code)).title()[:40]

        if_entries.append({
            "code":  code,
            "name":  name,
            "score": int(round(if_score)),
            "dir":   direction,
        })
        if abs(z) >= 1.0 or if_score >= 40:
            anomalies.append({
                "code":     code,
                "name":     name,
                "signal":   round(today_net / 1e6, 2),
                "baseline": round(mu / 1e6, 2),
                "z":        round(z, 1),
                "ifScore":  int(round(if_score)),
                "dir":      direction,
            })

    anomalies.sort(key=lambda r: max(abs(r["z"]), r["ifScore"] / 30), reverse=True)
    if_entries.sort(key=lambda r: r["score"])
    return anomalies, if_entries


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

    # Inject live AI insights banner + scoring date BEFORE the React scripts run.
    csv_files = sorted(glob.glob(str(OUTPUT_DIR / "scores_*.csv")))
    scoring_date = csv_files[-1].split("scores_")[-1].replace(".csv", "") if csv_files else ""

    pre_js = (
        f"<script>"
        f"window.AI_INSIGHTS = {json.dumps(build_ai_insights())};"
        f"window.SCORING_DATE = {json.dumps(scoring_date)};"
        f"</script>"
    )
    html = html.replace("<script src=\"https://unpkg.com/react@", pre_js + "\n  <script src=\"https://unpkg.com/react@", 1)

    # Inject real RANKINGS + watchlist anomalies AFTER data.js sets
    # window.IDX_DATA, BEFORE views.jsx reads from it.
    rankings = build_rankings()
    anomalies, if_entries = build_anomalies()
    overrides_js = (
        f"<script>"
        f"if (window.IDX_DATA) {{"
        f"  window.IDX_DATA.RANKINGS = {json.dumps(rankings)};"
        f"  window.IDX_DATA.ANOMALIES = {json.dumps(anomalies)};"
        f"  window.IDX_DATA.ISOLATION_FOREST = {json.dumps(if_entries)};"
        f"}}"
        f"</script>"
    )
    html = html.replace(
        '<script type="text/babel" data-presets="react">',
        overrides_js + '\n  <script type="text/babel" data-presets="react">',
        1,
    )

    return html


components.html(build_inlined_html(), height=1100, scrolling=True)
