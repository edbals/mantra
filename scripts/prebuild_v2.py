#!/usr/bin/env python3
"""
Pre-compute every IsolationForest + ranking + anomaly artifact the v2
dashboard needs, and save to output/v2_data_{date}.json.

Designed to be called from cron right after main.py finishes scoring:

    python3 main.py --incremental && python3 scripts/prebuild_v2.py

The dashboard reads the JSON directly, so each user request is just a file
read (no sklearn fits, no SQL queries on the request path).
"""
from __future__ import annotations

import argparse
import glob
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.anomaly import score_brokers   # noqa: E402

OUTPUT = ROOT / "output"


# ── helpers ──────────────────────────────────────────────────────────────────
def _f(v, default=0.0) -> float:
    try:
        f = float(v)
        return default if pd.isna(f) else f
    except (TypeError, ValueError):
        return default


def _xlxc(row) -> str:
    if row.get("xl_xc_selling"): return "net-sell"
    if row.get("xl_xc_buying"):  return "net-buy"
    return "balance"


def _anomaly_proxy(row) -> int:
    adj_raw = row.get("score_adj"); adj = 0.0 if pd.isna(adj_raw) else float(adj_raw or 0)
    s_raw = row.get("accum_streak"); streak = 0.0 if pd.isna(s_raw) else float(s_raw or 0)
    base = max(0.0, adj) * 3.0
    bonus = max(0.0, min(10.0, streak - 3) * 2.0)
    return int(min(100, base + bonus + abs(min(0.0, adj)) * 1.5))


def _broker_names() -> dict[str, str]:
    try:
        bm = pd.read_csv(ROOT / "broker_master.csv")
        col = next((c for c in bm.columns if c.strip().lower() in ("kode perusahaan","broker_code","code","kode")), None)
        ncol = next((c for c in bm.columns if c.strip().lower() in ("nama perusahaan","name","broker_name")), None)
        return dict(zip(bm[col].astype(str).str.strip(), bm[ncol])) if col and ncol else {}
    except Exception:
        return {}


# ── builders ─────────────────────────────────────────────────────────────────
def build_rankings(scores: pd.DataFrame) -> list[dict]:
    df = scores
    if "broker_data_source" in df.columns:
        df = df[df["broker_data_source"] == "indexalpha"].copy()
    df = df[df["action"] != "ILLIQUID"].copy()
    if df.empty: return []
    df = df.sort_values("investment_score", ascending=False).reset_index(drop=True)
    out = []
    for i, row in df.iterrows():
        name = row.get("company_name")
        if pd.isna(name) or not name: name = row["ticker"]
        out.append({
            "rank":          int(i + 1),
            "ticker":        str(row["ticker"]),
            "name":          str(name)[:60],
            "action":        str(row.get("action") or "OBSERVE"),
            "score":         round(_f(row.get("investment_score")), 1),
            "breakout":      bool(row.get("breakout_signal")) and not pd.isna(row.get("breakout_signal")),
            "brokerFlow":    round(_f(row.get("broker_flow_real_score")), 1),
            "floatPressure": round(_f(row.get("float_pressure_score")), 1),
            "anomaly":       _anomaly_proxy(row),
            "xlxc":          _xlxc(row),
            "close":         int(_f(row.get("close"))),
            "advB":          round(_f(row.get("avg_daily_value_idr")) / 1e9, 1),
            "trend":         0,
        })
    return out


def build_ai_insights(scores: pd.DataFrame) -> str:
    df = scores
    if "broker_data_source" in df.columns:
        df = df[df["broker_data_source"] == "indexalpha"]
    if df.empty: return ""
    parts = []
    n_invest = int((df.get("action", pd.Series(dtype=str)) == "INVEST").sum())
    if n_invest:
        parts.append(f"<b>{n_invest} INVEST signal{'s' if n_invest != 1 else ''}</b> active today.")
    if {"absorption_ratio","broker_flow_real_score"}.issubset(df.columns):
        absorbing = (df[(df["absorption_ratio"] > 1.5) & (df["broker_flow_real_score"] >= 60)]
                     .sort_values("broker_flow_real_score", ascending=False).head(3))
        if not absorbing.empty:
            t = ", ".join(f"<b>{x}</b>" for x in absorbing["ticker"].tolist())
            parts.append(f"Institutional absorption (&gt;1.5×) detected in {t}.")
    if "xl_xc_trend_selling" in df.columns:
        n = int(df["xl_xc_trend_selling"].fillna(False).astype(bool).sum())
        if n: parts.append(f"<b>Sustained retail exit</b> (Stockbit / Ajaib / Mirae) confirmed in {n} ticker{'s' if n != 1 else ''}.")
    if "accum_streak" in df.columns:
        n = int((df["accum_streak"].fillna(0) >= 3).sum())
        if n: parts.append(f"{n} tickers with 3+ day institutional accumulation streak.")
    return " ".join(parts) or "No notable broker-flow signals today across the Stage 2 universe."


def build_volume_anomalies(scores: pd.DataFrame, idxdb: Path, baseline_days: int = 22):
    if "broker_data_source" in scores.columns:
        scores = scores[scores["broker_data_source"] == "indexalpha"]
    scores = scores[scores["action"] != "ILLIQUID"]
    if scores.empty: return [], []
    tickers = scores["ticker"].tolist()
    name_map = dict(zip(scores["ticker"], scores.get("company_name", scores["ticker"])))

    con = sqlite3.connect(str(idxdb), check_same_thread=False)
    placeholders = ",".join("?" * len(tickers))
    cutoff_ms = int((pd.Timestamp.now() - pd.Timedelta(days=baseline_days * 2 + 10)).timestamp() * 1000)
    try:
        df = pd.read_sql_query(
            f"""SELECT code AS ticker, date AS date_ms, open, high, low, close, volume, value
                FROM stock_summary WHERE code IN ({placeholders}) AND date >= ? AND volume > 0
                ORDER BY code, date""",
            con, params=(*tickers, cutoff_ms))
    finally:
        con.close()
    if df.empty: return [], []

    df["date"] = pd.to_datetime(df["date_ms"], unit="ms").dt.date
    df = df.sort_values(["ticker", "date"])
    df["prev_close"]    = df.groupby("ticker")["close"].shift(1)
    df["close_chg_pct"] = (df["close"] - df["prev_close"]) / df["prev_close"]
    df["range_pct"]     = (df["high"] - df["low"]) / df["close"]
    df["vol_ma20"]      = df.groupby("ticker")["volume"].transform(lambda s: s.rolling(20, min_periods=5).mean())
    df["rel_volume"]    = df["volume"] / df["vol_ma20"]
    df = df.dropna(subset=["close_chg_pct","rel_volume","range_pct"])
    if df.empty: return [], []

    today = df["date"].max()
    baseline = df[df["date"] < today]
    signal   = df[df["date"] == today]

    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    FEATS = ["volume","value","rel_volume","range_pct","close_chg_pct"]

    rows = []
    for ticker, sg in signal.groupby("ticker"):
        hist = baseline[baseline["ticker"] == ticker]
        if len(hist) < 15: continue
        sig_row = sg.iloc[0]
        vol_mean, vol_std = float(hist["volume"].mean()), float(hist["volume"].std()) or 1.0
        z = (float(sig_row["volume"]) - vol_mean) / vol_std
        try:
            scaler = StandardScaler().fit(hist[FEATS].values)
            model = IsolationForest(n_estimators=120, contamination=0.05, random_state=42)
            model.fit(scaler.transform(hist[FEATS].values))
            raw = float(model.decision_function(scaler.transform(sg[FEATS].values))[0])
            if_score = float(np.clip((-raw + 0.5) * 100, 0, 100))
        except Exception:
            if_score = 0.0
        chg = float(sig_row["close_chg_pct"])
        rows.append({
            "ticker": ticker, "name": str(name_map.get(ticker, ticker))[:40],
            "vol_today": float(sig_row["volume"]), "vol_mean": vol_mean,
            "z": z, "if_score": if_score,
            "dir": "buy" if chg >= 0 else "sell",
        })

    anomalies, if_entries = [], []
    for r in rows:
        if_int = int(round(r["if_score"]))
        if_entries.append({"code": r["ticker"], "name": r["name"], "score": if_int, "dir": r["dir"]})
        if abs(r["z"]) >= 1.5 or r["if_score"] >= 50:
            anomalies.append({
                "code": r["ticker"], "name": r["name"],
                "signal":   round(r["vol_today"]/1e6, 2),
                "baseline": round(r["vol_mean"]/1e6, 2),
                "z":        round(r["z"], 1),
                "ifScore":  if_int, "dir": r["dir"],
            })
    anomalies.sort(key=lambda r: (r["ifScore"], abs(r["z"])), reverse=True)
    if_entries.sort(key=lambda r: r["score"], reverse=True)
    return anomalies, if_entries[:15]


def build_per_ticker_broker_if(scores: pd.DataFrame) -> dict[str, list[dict]]:
    if "broker_data_source" in scores.columns:
        scores = scores[scores["broker_data_source"] == "indexalpha"]
    scores = scores[scores["action"] != "ILLIQUID"]
    if scores.empty: return {}
    tickers = scores["ticker"].tolist()
    db_path = OUTPUT / "scores.db"
    if not db_path.exists(): return {}

    names = _broker_names()
    con = sqlite3.connect(str(db_path))
    placeholders = ",".join("?" * len(tickers))
    df = pd.read_sql_query(
        f"""SELECT date, ticker, broker_code AS code, buy_volume, sell_volume
            FROM broker_transactions WHERE ticker IN ({placeholders}) AND investor_type='all'""",
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
        hist, sig = grp[grp["date"] < today], grp[grp["date"] == today]
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
                "code": code,
                "name": str(names.get(code, code)).title()[:40],
                "score": int(round(float(sr["anomaly_score"]))),
                "z":    round(z, 1),
                "dir":  str(sr["direction"]),
            })
        out[ticker] = rows
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="YYYY-MM-DD; defaults to latest scored date")
    p.add_argument("--idxdb", default=str(ROOT / "IDX-API/data/database.sqlite"))
    args = p.parse_args()

    csvs = sorted(glob.glob(str(OUTPUT / "scores_*.csv")))
    if not csvs:
        print("no scores CSV found", file=sys.stderr); sys.exit(1)

    if args.date:
        target = OUTPUT / f"scores_{args.date}.csv"
        if not target.exists():
            print(f"missing {target}", file=sys.stderr); sys.exit(1)
        csv_path = target
    else:
        csv_path = Path(csvs[-1])

    scoring_date = csv_path.stem.replace("scores_", "")
    print(f"prebuilding v2 data for {scoring_date}...", flush=True)

    scores = pd.read_csv(csv_path)
    available = sorted([Path(c).stem.replace("scores_", "") for c in csvs], reverse=True)

    rankings        = build_rankings(scores)
    ai_insights     = build_ai_insights(scores)
    anomalies, ifs  = build_volume_anomalies(scores, Path(args.idxdb))
    broker_if       = build_per_ticker_broker_if(scores)

    payload = {
        "scoring_date":     scoring_date,
        "available_dates":  available,
        "ai_insights":      ai_insights,
        "rankings":         rankings,
        "anomalies":        anomalies,
        "isolation_forest": ifs,
        "broker_if_by_ticker": broker_if,
    }

    out_file = OUTPUT / f"v2_data_{scoring_date}.json"
    out_file.write_text(json.dumps(payload, separators=(",", ":")))
    (OUTPUT / "v2_data_latest.json").write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {out_file} ({out_file.stat().st_size // 1024}KB)", flush=True)


if __name__ == "__main__":
    main()
