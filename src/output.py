from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_CSV_COLUMNS = [
    "date", "ticker", "company_name", "action",
    "investment_score", "breakout_signal",
    "broker_flow_score", "float_pressure_score", "structure_score",
    "liquidity_score", "catalyst_score",
    "free_float_pct", "ff_category", "effective_float_shares", "avg_daily_value_idr",
    "close", "volume", "volume_ratio", "above_ma20", "accum_streak",
    # Broker presence (Stage 2 — real Index Alpha data, proxy score unchanged)
    "broker_data_source",
    "broker_flow_real_score",
    "top_buyers", "top_sellers",
    "inst_net_vol_today", "retail_net_vol_today",
    "retail_sell_share", "absorption_ratio", "accum_streak",
    "xl_xc_selling", "xl_xc_buying", "xl_xc_trend_days", "xl_xc_trend_selling",
    "sustained_buyers", "score_adj",
    # Informational (Q3 default)
    "net_flow_1d", "net_flow_3d", "net_flow_5d", "net_flow_10d",
]


def write_csv(df: pd.DataFrame, date_str: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"scores_{date_str}.csv"
    out = df.copy()
    out["date"] = date_str

    # Only include columns that exist
    cols = [c for c in _CSV_COLUMNS if c in out.columns]
    out = out[cols].sort_values("investment_score", ascending=False)
    # Round scores to 2 decimal places
    score_cols = [c for c in cols if c.endswith("_score")]
    out[score_cols] = out[score_cols].round(2)

    out.to_csv(path, index=False)
    logger.info("CSV written: %s (%d rows)", path.name, len(out))
    return path


def write_json(df: pd.DataFrame, date_str: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"summary_{date_str}.json"

    action_groups = {a: [] for a in ["INVEST", "WATCH_EXEC", "WATCH", "OBSERVE"]}
    for action, group in df.groupby("action"):
        if action in action_groups:
            action_groups[action] = group["ticker"].tolist()

    top10 = df.nlargest(10, "investment_score")
    top10_list = []
    for _, row in top10.iterrows():
        entry = {
            "ticker": row["ticker"],
            "action": row.get("action", ""),
            "investment_score": round(float(row["investment_score"]), 2),
            "breakout_signal": bool(row.get("breakout_signal", False)),
            "broker_flow_score": round(float(row.get("broker_flow_score", 0)), 2),
        }
        if "free_float_pct" in row and pd.notna(row["free_float_pct"]):
            entry["free_float_pct"] = round(float(row["free_float_pct"]) * 100, 1)
        top10_list.append(entry)

    summary = {
        "date": date_str,
        "scoring_date": date_str,
        "total_screened": len(df),
        "invest": action_groups["INVEST"],
        "watch_exec": action_groups["WATCH_EXEC"],
        "watch": action_groups["WATCH"],
        "top10": top10_list,
    }

    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("JSON written: %s", path.name)
    return path
