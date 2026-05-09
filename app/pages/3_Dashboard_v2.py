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


def _csv_mtime() -> float:
    """Cache key — invalidate when the latest scores CSV changes."""
    csvs = glob.glob(str(OUTPUT_DIR / "scores_*.csv"))
    return max((Path(c).stat().st_mtime for c in csvs), default=0.0)


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


@st.cache_data(ttl=3600, show_spinner=False)
def build_per_ticker_broker_if(_csv_key: float) -> dict[str, list[dict]]:
    """
    For each Stage 2 ticker, run IsolationForest per broker on its history
    and return today's anomaly score. Output: {ticker: [{code, name, score,
    z, dir}, ...]}, top 10 brokers per ticker by IF score.
    Cached — runs once per CSV update.
    """
    sys_path = str(Path(__file__).parent.parent.parent)
    import sys as _sys
    if sys_path not in _sys.path: _sys.path.insert(0, sys_path)
    from src.anomaly import score_brokers

    csv_path = pick_csv(None)
    if csv_path is None: return {}
    scores = pd.read_csv(csv_path)
    if "broker_data_source" in scores.columns:
        scores = scores[scores["broker_data_source"] == "indexalpha"]
    scores = scores[scores["action"] != "ILLIQUID"]
    if scores.empty: return {}
    tickers = scores["ticker"].tolist()

    db_path = OUTPUT_DIR / "scores.db"
    if not db_path.exists(): return {}

    # Load broker name lookup
    try:
        bm = pd.read_csv(Path(__file__).parent.parent.parent / "broker_master.csv")
        col = next((c for c in bm.columns if c.strip().lower() in ("kode perusahaan", "broker_code", "code", "kode")), None)
        ncol = next((c for c in bm.columns if c.strip().lower() in ("nama perusahaan", "name", "broker_name")), None)
        names = dict(zip(bm[col].astype(str).str.strip(), bm[ncol])) if col and ncol else {}
    except Exception:
        names = {}

    con = sqlite3.connect(str(db_path))
    placeholders = ",".join("?" * len(tickers))
    df = pd.read_sql_query(
        f"""
        SELECT date, ticker, broker_code AS code, buy_volume, sell_volume
        FROM broker_transactions
        WHERE ticker IN ({placeholders}) AND investor_type='all'
        """,
        con, params=tickers,
    )
    con.close()
    if df.empty: return {}
    df["net_volume"] = df["buy_volume"].fillna(0) - df["sell_volume"].fillna(0)

    out = {}
    for ticker, grp in df.groupby("ticker"):
        dates = sorted(grp["date"].unique())
        if len(dates) < 6: continue
        today = dates[-1]
        hist  = grp[grp["date"] < today]
        sig   = grp[grp["date"] == today]
        if hist.empty or sig.empty: continue

        try:
            scored = score_brokers(hist, sig, contamination=0.05)
        except Exception:
            continue
        if scored.empty: continue

        rows = []
        for _, sr in scored.sort_values("anomaly_score", ascending=False).head(10).iterrows():
            code = str(sr["code"])
            today_net = float(sig[sig["code"] == code]["net_volume"].sum())
            hist_net  = hist[hist["code"] == code]["net_volume"]
            mu, sd = float(hist_net.mean()), float(hist_net.std() or 1.0)
            z = (today_net - mu) / sd if sd else 0.0
            rows.append({
                "code":  code,
                "name":  str(names.get(code, code)).title()[:40],
                "score": int(round(float(sr["anomaly_score"]))),
                "z":     round(z, 1),
                "dir":   str(sr["direction"]),
            })
        out[ticker] = rows
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_anomalies(_csv_key: float, baseline_days: int = 22) -> tuple[list[dict], list[dict]]:
    return _build_anomalies_uncached(baseline_days)


def build_anomalies(baseline_days: int = 22) -> tuple[list[dict], list[dict]]:
    """Cached wrapper — re-runs only when the latest scores CSV changes."""
    return _cached_anomalies(_csv_mtime(), baseline_days)


def _build_anomalies_uncached(baseline_days: int = 22) -> tuple[list[dict], list[dict]]:
    """
    Per-STOCK volume anomaly detection across the Stage 2 universe.
    Finds tickers whose today's volume is statistically unusual vs their
    own 22-day baseline. Uses sklearn IsolationForest on (volume, value,
    rel_volume_20d, range_pct, close_chg_pct) — fit on baseline only.

    Direction reflects today's price move (close vs prev close):
      "buy"  = volume spike on an up day  (likely accumulation/breakout)
      "sell" = volume spike on a down day (likely distribution/capitulation)

    Returns (anomalies, isolation_forest):
      - anomalies: rows where |z| >= 1.5 OR IF score >= 50
      - isolation_forest: top ~12 tickers by IF score for the chart
    """
    config_path = Path(__file__).parent.parent.parent / "config.json"
    if not config_path.exists():
        return [], []
    cfg = json.loads(config_path.read_text())

    idxdb_raw = cfg.get("idxdb_path", "")
    idxdb = Path(idxdb_raw) if idxdb_raw.startswith("/") else (Path(__file__).parent.parent.parent / idxdb_raw)
    if not idxdb.exists():
        return [], []

    csv_path = pick_csv(None)
    if csv_path is None:
        return [], []
    scores = pd.read_csv(csv_path)
    if "broker_data_source" in scores.columns:
        scores = scores[scores["broker_data_source"] == "indexalpha"]
    scores = scores[scores["action"] != "ILLIQUID"]
    if scores.empty:
        return [], []
    tickers = scores["ticker"].tolist()
    name_map = dict(zip(scores["ticker"], scores.get("company_name", scores["ticker"])))

    # Pull last ~30 trading days of OHLCV for these tickers
    con = sqlite3.connect(str(idxdb), check_same_thread=False)
    placeholders = ",".join("?" * len(tickers))
    cutoff_ms = int((pd.Timestamp.now() - pd.Timedelta(days=baseline_days * 2 + 10)).timestamp() * 1000)
    try:
        df = pd.read_sql_query(
            f"""
            SELECT code AS ticker, date AS date_ms, open, high, low, close, volume, value
            FROM stock_summary
            WHERE code IN ({placeholders})
              AND date >= ?
              AND volume > 0
            ORDER BY code, date
            """,
            con, params=(*tickers, cutoff_ms),
        )
    finally:
        con.close()

    if df.empty:
        return [], []

    df["date"] = pd.to_datetime(df["date_ms"], unit="ms").dt.date
    df = df.sort_values(["ticker", "date"])

    # Per-ticker rolling features
    df["prev_close"]    = df.groupby("ticker")["close"].shift(1)
    df["close_chg_pct"] = (df["close"] - df["prev_close"]) / df["prev_close"]
    df["range_pct"]     = (df["high"] - df["low"]) / df["close"]
    df["vol_ma20"]      = df.groupby("ticker")["volume"].transform(lambda s: s.rolling(20, min_periods=5).mean())
    df["rel_volume"]    = df["volume"] / df["vol_ma20"]

    df = df.dropna(subset=["close_chg_pct", "rel_volume", "range_pct"])
    if df.empty:
        return [], []

    # Latest date in IDX is "today" for this analysis
    today = df["date"].max()
    baseline = df[df["date"] < today].copy()
    signal   = df[df["date"] == today].copy()

    # Real IsolationForest per-ticker — fit on baseline only
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    FEATS = ["volume", "value", "rel_volume", "range_pct", "close_chg_pct"]
    MIN_BASELINE = 15

    rows = []
    for ticker, sig_grp in signal.groupby("ticker"):
        hist = baseline[baseline["ticker"] == ticker]
        if len(hist) < MIN_BASELINE:
            continue
        sig_row = sig_grp.iloc[0]

        # z-score on volume vs baseline volume
        vol_mean = float(hist["volume"].mean())
        vol_std  = float(hist["volume"].std()) or 1.0
        z = (float(sig_row["volume"]) - vol_mean) / vol_std

        # IsolationForest
        try:
            X_h = hist[FEATS].values
            X_s = sig_grp[FEATS].values
            scaler = StandardScaler().fit(X_h)
            model = IsolationForest(n_estimators=120, contamination=0.05, random_state=42)
            model.fit(scaler.transform(X_h))
            raw = float(model.decision_function(scaler.transform(X_s))[0])
            if_score = float(np.clip((-raw + 0.5) * 100, 0, 100))
        except Exception:
            if_score = 0.0

        chg = float(sig_row["close_chg_pct"])
        direction = "buy" if chg >= 0 else "sell"

        rows.append({
            "ticker":    ticker,
            "name":      str(name_map.get(ticker, ticker))[:40],
            "vol_today": float(sig_row["volume"]),
            "vol_mean":  vol_mean,
            "z":         z,
            "if_score":  if_score,
            "dir":       direction,
            "chg_pct":   chg,
        })

    if not rows:
        return [], []

    # Build the two output arrays
    anomalies = []
    if_entries = []
    for r in rows:
        anom_signal_m = round(r["vol_today"] / 1e6, 2)   # M lots
        anom_baseline_m = round(r["vol_mean"] / 1e6, 2)
        if_score_int = int(round(r["if_score"]))
        z_round = round(r["z"], 1)

        if_entries.append({
            "code":  r["ticker"],
            "name":  r["name"],
            "score": if_score_int,
            "dir":   r["dir"],
        })
        if abs(r["z"]) >= 1.5 or r["if_score"] >= 50:
            anomalies.append({
                "code":     r["ticker"],
                "name":     r["name"],
                "signal":   anom_signal_m,
                "baseline": anom_baseline_m,
                "z":        z_round,
                "ifScore":  if_score_int,
                "dir":      r["dir"],
            })

    # Top anomalies first; for IF chart show top 15 most anomalous
    anomalies.sort(key=lambda r: (r["ifScore"], abs(r["z"])), reverse=True)
    if_entries.sort(key=lambda r: r["score"], reverse=True)
    if_entries = if_entries[:15]

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


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_inlined_html(_csv_key: float, requested_date: str | None) -> str:
    return _build_inlined_html_uncached(requested_date)


def build_inlined_html(requested_date: str | None = None) -> str:
    """Cached wrapper — rebuild only when CSV changes or date param differs."""
    return _cached_inlined_html(_csv_mtime(), requested_date or "")


def _load_prebuilt(requested_date: str | None) -> dict | None:
    """Load the JSON artifact written by scripts/prebuild_v2.py."""
    if requested_date:
        f = OUTPUT_DIR / f"v2_data_{requested_date}.json"
        if f.exists(): return json.loads(f.read_text())
    f = OUTPUT_DIR / "v2_data_latest.json"
    return json.loads(f.read_text()) if f.exists() else None


def _build_inlined_html_uncached(requested_date: str | None = None) -> str:
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

    # Read prebuilt JSON; fall back to on-demand compute if it's missing
    payload = _load_prebuilt(requested_date)
    if payload is None:
        csv_path = pick_csv(requested_date or None)
        scoring_date = csv_path.stem.replace("scores_", "") if csv_path else ""
        payload = {
            "scoring_date":         scoring_date,
            "available_dates":      list_scored_dates(),
            "ai_insights":          build_ai_insights(),
            "rankings":             build_rankings(csv_path),
            "anomalies":            [],
            "isolation_forest":     [],
            "broker_if_by_ticker":  {},
        }
        a, ifs = build_anomalies()
        payload["anomalies"] = a
        payload["isolation_forest"] = ifs
        payload["broker_if_by_ticker"] = build_per_ticker_broker_if(_csv_mtime())

    pre_js = (
        f"<script>"
        f"window.AI_INSIGHTS    = {json.dumps(payload['ai_insights'])};"
        f"window.SCORING_DATE   = {json.dumps(payload['scoring_date'])};"
        f"window.AVAILABLE_DATES = {json.dumps(payload['available_dates'])};"
        f"</script>"
    )
    html = html.replace("<script src=\"https://unpkg.com/react@", pre_js + "\n  <script src=\"https://unpkg.com/react@", 1)

    overrides_js = (
        f"<script>"
        f"if (window.IDX_DATA) {{"
        f"  window.IDX_DATA.RANKINGS = {json.dumps(payload['rankings'])};"
        f"  window.IDX_DATA.ANOMALIES = {json.dumps(payload['anomalies'])};"
        f"  window.IDX_DATA.ISOLATION_FOREST = {json.dumps(payload['isolation_forest'])};"
        f"  window.IDX_DATA.BROKER_IF_BY_TICKER = {json.dumps(payload['broker_if_by_ticker'])};"
        f"}}"
        f"</script>"
    )
    html = html.replace(
        '<script type="text/babel" data-presets="react">',
        overrides_js + '\n  <script type="text/babel" data-presets="react">',
        1,
    )

    return html


_requested = ""
try:
    _requested = st.query_params.get("date") or ""
except Exception:
    pass
components.html(build_inlined_html(_requested), height=1100, scrolling=True)
