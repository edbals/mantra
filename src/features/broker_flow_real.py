"""
Real Broker Flow Scoring — Stage 2
====================================
Uses Index Alpha per-ticker broker transaction data to replace the proxy
broker_flow_score for the top tickers selected by FF x ADV blend_score.

Presence boost (applied when broker class has net buying above its own avg):
    Market_Maker  → +12  (leads price moves — strongest signal)
    Emitent       → +10  (owner/insider accumulation)
    institutional → +8   (large block buying)
    Zombie        → +6   (unusual buying from crossing brokers — worth noting)
    Capped at +30 total from presence boosts.

Penalty:
    XL or XC in top 3 sellers  → -15  (known distribution brokers)

Retail classes (retail_pure, retail_mixed, unknown) are not boosted or penalised
— their signal is captured in retail_sell_share and absorption_ratio.

Broker Presence Indicator flags shown in top_buyers / top_sellers strings:
    [MM]   = Market_Maker
    [EMIT] = Emitent
    [ZOM]  = Zombie
    (institutional = expected, no flag clutter)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.indexalpha import IndexAlphaClient

logger = logging.getLogger(__name__)

# All classes where above-average buying is a positive signal
SIGNAL_CLASSES = {"institutional", "Market_Maker", "Emitent", "Zombie"}
RETAIL_CLASSES = {"retail_pure", "retail_mixed"}

# Human-readable labels for the broker code suffix in top_buyers / top_sellers.
# "Zombie" is renamed to "crossing" — it's the formal term for brokers running
# crossing networks rather than directional flow.
CLASS_DISPLAY = {
    "institutional":  "institutional",
    "Market_Maker":   "market maker",
    "Emitent":        "insider",
    "Zombie":         "crossing",
    "retail_pure":    "retail",
    "retail_mixed":   "retail",
}

# Boost per broker of each class that is buying above its historical average
CLASS_BOOST = {
    "Market_Maker":  12,
    "Emitent":       10,
    "institutional":  8,
    "Zombie":         6,
}
MAX_PRESENCE_BOOST = 30

ADJ_XL_XC_SELLING = +15   # retail exiting → smart money absorbing → bullish
ADJ_XL_XC_BUYING  = -15   # retail piling in → distribution → bearish
XL_XC_TREND_DAYS  = 3     # min days of retail net selling in last 10 to flag trend

# Retail platform broker codes used for the "retail trend" signal.
# XL = Stockbit, XC = Ajaib (pure retail apps).
# YP = Mirae (retail_mixed; dominant retail base via HOTS app).
RETAIL_PLATFORMS = ("XL", "XC", "YP")

# z-score threshold to consider a broker "buying above average"
Z_THRESH        = 1.5
MIN_HISTORY_DAYS = 20   # <20 gives ~30% std error on σ; 20 is the practical minimum

# Normalisation caps
RETAIL_SELL_CAP = 0.30   # 30% retail net selling of total vol = max
ABSORPTION_CAP  = 2.0    # 2:1 institutional/retail absorption = max
STREAK_CAP      = 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _classify(df: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    master_map = master.set_index("broker_code")["broker_class"].to_dict()
    df = df.copy()
    df["cls"] = df["code"].map(master_map).fillna("unknown")
    return df


def _group_net(df: pd.DataFrame, classes: set) -> float:
    if df.empty:
        return 0.0
    return float(df[df["cls"].isin(classes)]["net_volume"].fillna(0).sum())


def _format_presence(df: pd.DataFrame, vol_col: str, top_n: int = 3, signed: bool = True) -> str:
    parts = []
    for _, row in df.head(top_n).iterrows():
        cls_label = CLASS_DISPLAY.get(row["cls"], "")
        vol = int(row.get(vol_col, 0) or 0)
        suffix = f" ({cls_label})" if cls_label else ""
        vol_str = f"{vol:+,}" if signed else f"{vol:,}"
        parts.append(f"{row['code']}{suffix} {vol_str}")
    return "   ·   ".join(parts)


def _compute_streak(ticker: str, scoring_date: str, client: "IndexAlphaClient", master: pd.DataFrame) -> int:
    """Consecutive trailing days where SIGNAL_CLASSES brokers were net buyers."""
    con = client._connect()
    df = pd.read_sql_query(
        """
        SELECT date, broker_code, buy_volume, sell_volume
        FROM broker_transactions
        WHERE ticker=? AND investor_type='all' AND date <= ?
        ORDER BY date DESC LIMIT 300
        """,
        con, params=(ticker, scoring_date),
    )
    con.close()
    if df.empty:
        return 0

    master_map = master.set_index("broker_code")["broker_class"].to_dict()
    df["cls"] = df["broker_code"].map(master_map).fillna("unknown")
    df["net"] = df["buy_volume"].fillna(0) - df["sell_volume"].fillna(0)

    daily = (
        df[df["cls"].isin(SIGNAL_CLASSES)]
        .groupby("date")["net"].sum()
        .sort_index(ascending=False)
    )
    streak = 0
    for net in daily:
        if net > 0:
            streak += 1
        else:
            break
    return min(streak, STREAK_CAP)


def _compute_xl_xc_trend(ticker: str, scoring_date: str, client: "IndexAlphaClient") -> tuple[int, bool]:
    """
    Returns (selling_days, trend_flag) for retail platforms (XL/XC/YP) over
    the last 10 trading days. selling_days = days the combined retail net
    was negative. trend_flag = True if selling_days >= XL_XC_TREND_DAYS.
    """
    placeholders = ",".join("?" * len(RETAIL_PLATFORMS))
    con = client._connect()
    df = pd.read_sql_query(
        f"""
        SELECT date, broker_code, buy_volume, sell_volume
        FROM broker_transactions
        WHERE ticker=? AND investor_type='all'
          AND broker_code IN ({placeholders}) AND date <= ?
        ORDER BY date DESC LIMIT 200
        """,
        con, params=(ticker, *RETAIL_PLATFORMS, scoring_date),
    )
    con.close()
    if df.empty:
        return 0, False

    df["net"] = df["buy_volume"].fillna(0) - df["sell_volume"].fillna(0)
    daily = df.groupby("date")["net"].sum().sort_index(ascending=False).head(10)
    selling_days = int((daily < 0).sum())
    return selling_days, selling_days >= XL_XC_TREND_DAYS


def _compute_zscores(
    ticker: str,
    scoring_date: str,
    client: "IndexAlphaClient",
    master: pd.DataFrame,
) -> dict[str, tuple[float, str]]:
    """
    Return {broker_code: (z_score, broker_class)} for SIGNAL_CLASSES brokers
    with sufficient history. Only brokers with z >= Z_THRESH are included.
    """
    con = client._connect()
    df = pd.read_sql_query(
        """
        SELECT date, broker_code, buy_volume, sell_volume
        FROM broker_transactions
        WHERE ticker=? AND investor_type='all' AND date <= ?
        ORDER BY date DESC LIMIT 600
        """,
        con, params=(ticker, scoring_date),
    )
    con.close()
    if df.empty:
        return {}

    master_map = master.set_index("broker_code")["broker_class"].to_dict()
    df["cls"] = df["broker_code"].map(master_map).fillna("unknown")
    df["net"] = df["buy_volume"].fillna(0) - df["sell_volume"].fillna(0)
    df = df[df["cls"].isin(SIGNAL_CLASSES)]
    if df.empty:
        return {}

    today_rows = df[df["date"] == scoring_date]
    hist_rows  = df[df["date"] < scoring_date]

    results = {}
    for code in today_rows["broker_code"].unique():
        cls       = master_map.get(code, "unknown")
        today_net = today_rows[today_rows["broker_code"] == code]["net"].sum()
        hist      = hist_rows[hist_rows["broker_code"] == code]["net"]
        if len(hist) < MIN_HISTORY_DAYS:
            continue
        mu, sigma = hist.mean(), hist.std()
        if sigma > 0:
            z = float((today_net - mu) / sigma)
            if z >= Z_THRESH:
                results[code] = (z, cls)
    return results


# ── Per-ticker scorer ─────────────────────────────────────────────────────────

def score_ticker(
    ticker: str,
    scoring_date: str,
    from_date: str,
    client: "IndexAlphaClient",
    broker_master_df: pd.DataFrame,
) -> dict:
    eps    = 1e-9
    master = broker_master_df.copy()

    today_df  = _classify(client.get_broker_summary(ticker, scoring_date), master)
    period_df = _classify(client.get_period_summary(ticker, from_date, scoring_date), master)

    if today_df.empty and period_df.empty:
        return {"ticker": ticker, "broker_data_source": "proxy"}

    # ── Period signals (20-day window — more stable than single day) ──────────
    period_total_vol   = float(
        period_df["buy_volume"].fillna(0).sum() + period_df["sell_volume"].fillna(0).sum()
    ) if not period_df.empty else 0.0
    period_inst_net    = _group_net(period_df, SIGNAL_CLASSES)
    period_retail_net  = _group_net(period_df, RETAIL_CLASSES)

    retail_selling     = max(0.0, -period_retail_net)
    retail_sell_share  = retail_selling / (period_total_vol + eps)
    retail_sell_norm   = min(retail_sell_share / RETAIL_SELL_CAP, 1.0)

    absorption_ratio   = period_inst_net / (retail_selling + eps) if retail_selling > 0 else 0.0
    absorption_norm    = min(max(absorption_ratio, 0.0) / ABSORPTION_CAP, 1.0)

    period_accum_norm  = min(max(period_inst_net, 0.0) / (period_total_vol * 0.05 + eps), 1.0)

    # ── Today snapshot (for display and today-specific signals only) ──────────
    total_vol_today  = float(
        today_df["buy_volume"].fillna(0).sum() + today_df["sell_volume"].fillna(0).sum()
    ) if not today_df.empty else 0.0
    inst_net_today   = _group_net(today_df, SIGNAL_CLASSES)
    retail_net_today = _group_net(today_df, RETAIL_CLASSES)

    # ── Streak ────────────────────────────────────────────────────────────────
    streak      = _compute_streak(ticker, scoring_date, client, master)
    streak_norm = streak / STREAK_CAP

    # ── Base score ────────────────────────────────────────────────────────────
    base_score = (
        retail_sell_norm  * 30
        + absorption_norm * 25
        + period_accum_norm * 25
        + streak_norm     * 20
    )

    # ── Broker Presence Indicator ─────────────────────────────────────────────
    # Rank by NET volume (buy - sell), not gross volume. Otherwise a broker that
    # buys 1M and sells 1M shows up in both lists despite contributing nothing.
    if not today_df.empty:
        today_df = today_df.copy()
        today_df["net_vol"] = today_df["buy_volume"].fillna(0) - today_df["sell_volume"].fillna(0)
        top_buyers_df  = today_df.nlargest(3,  "net_vol")[["code", "net_vol", "cls"]]
        top_sellers_df = today_df.nsmallest(3, "net_vol")[["code", "net_vol", "cls"]]
    else:
        top_buyers_df  = pd.DataFrame()
        top_sellers_df = pd.DataFrame()

    top_buyers_str  = _format_presence(top_buyers_df,  "net_vol")
    top_sellers_str = _format_presence(top_sellers_df, "net_vol")

    seller_codes     = set(top_sellers_df["code"].tolist()) if not top_sellers_df.empty else set()
    top3_buyer_codes = set(top_buyers_df["code"].tolist()) if not top_buyers_df.empty else set()

    # ── Score adjustments ─────────────────────────────────────────────────────
    adj = 0.0

    # Presence boost: each SIGNAL_CLASS broker buying above its own historical avg
    above_avg = _compute_zscores(ticker, scoring_date, client, master)
    presence_boost = 0.0
    for code, (z, cls) in above_avg.items():
        presence_boost += CLASS_BOOST.get(cls, 0)
    adj += min(presence_boost, MAX_PRESENCE_BOOST)

    # Retail platform selling = bullish (retail exiting, smart money absorbing)
    xl_xc_selling = bool(set(RETAIL_PLATFORMS) & seller_codes)
    if xl_xc_selling:
        adj += ADJ_XL_XC_SELLING  # +15

    # Retail platform buying = bearish (retail piling in, smart money distributing)
    xl_xc_buying = bool(set(RETAIL_PLATFORMS) & top3_buyer_codes)
    if xl_xc_buying:
        adj += ADJ_XL_XC_BUYING   # -15

    # Retail trend: how many of last 10 days were retail platforms net selling?
    xl_xc_trend_days, xl_xc_trend_selling = _compute_xl_xc_trend(ticker, scoring_date, client)

    final_score = float(np.clip(base_score + adj, 0.0, 100.0))

    # Human-readable sustained buyers list
    sustained_buyers = [
        f"{code} ({CLASS_DISPLAY.get(cls, '')}, z={z:.1f})"
        for code, (z, cls) in sorted(above_avg.items(), key=lambda x: -x[1][0])
    ]

    return {
        "ticker":                ticker,
        "broker_data_source":    "indexalpha",
        "broker_flow_score":     round(final_score, 2),
        "inst_net_vol_today":    round(inst_net_today, 0),
        "retail_net_vol_today":  round(retail_net_today, 0),
        "retail_sell_share":     round(retail_sell_share, 4),
        "absorption_ratio":      round(absorption_ratio, 4),
        "absorption_ratio_norm": round(absorption_norm, 4),
        "accum_streak":          streak,
        "accum_streak_norm":     round(streak_norm, 4),
        "top_buyers":            top_buyers_str,
        "top_sellers":           top_sellers_str,
        "xl_xc_selling":         xl_xc_selling,
        "xl_xc_buying":          xl_xc_buying,
        "xl_xc_trend_days":      xl_xc_trend_days,
        "xl_xc_trend_selling":   xl_xc_trend_selling,
        "sustained_buyers":      ", ".join(sustained_buyers),
        "score_adj":             round(adj, 2),
    }


# ── Batch entry point ─────────────────────────────────────────────────────────

def compute_real(
    tickers: list[str],
    scoring_date: str,
    from_date: str,
    client: "IndexAlphaClient",
    broker_master_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for i, ticker in enumerate(tickers):
        try:
            row = score_ticker(ticker, scoring_date, from_date, client, broker_master_df)
            score = row.get("broker_flow_score", 0)
            src   = row.get("broker_data_source", "?")
            print(f"  [{i+1:>3}/{len(tickers)}] {ticker:<8} score={score:5.1f}  src={src}", flush=True)
        except Exception as exc:
            logger.warning("broker_flow_real failed for %s: %s", ticker, exc)
            row = {"ticker": ticker, "broker_data_source": "proxy"}
            print(f"  [{i+1:>3}/{len(tickers)}] {ticker:<8} FAILED — proxy fallback", flush=True)
        rows.append(row)

    return pd.DataFrame(rows).set_index("ticker")
