from __future__ import annotations

"""
Broker Flow Feature — adapted for IDX-API data availability.

The IDX-API broker_summary table is a market-wide broker aggregate (no per-ticker
breakdown). We therefore approximate MyMantra broker flow signals using the columns
that ARE available in stock_summary on a per-ticker basis:

    foreign_buy / foreign_sell / foreign_net  → institutional flow proxy
    bid_volume / offer_volume                 → buy vs sell pressure
    volume, close, high, low                  → price/volume structure

Mapping:
    retail_sell_share  → offer_volume / (bid_volume + offer_volume)   [more offers = selling]
    absorption_ratio   → foreign_buy / (offer_volume * 100 + ε)       [foreign absorbing offers]
    accum_streak       → consecutive days with foreign_net > 0
    fragmentation      → high-volume strong-close days (concentrated buying proxy)
"""

import numpy as np
import pandas as pd


def compute(stock_df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    Compute broker-flow proxy features per ticker.

    Parameters
    ----------
    stock_df : DataFrame with columns:
               [ticker, date, close, high, low, volume,
                bid_volume, offer_volume, foreign_buy, foreign_sell, foreign_net]
               sorted by ticker, date ascending.
    lookback : rolling window in trading days

    Returns
    -------
    DataFrame indexed by ticker with columns:
        retail_sell_share, absorption_ratio_norm, accum_streak, accum_streak_norm,
        fragmentation_norm, net_flow_1d, net_flow_3d, net_flow_5d, net_flow_10d,
        broker_flow_score
    """
    df = stock_df.copy().sort_values(["ticker", "date"])
    eps = 1e-9

    # ── Retail sell share proxy (0–1): high offer pressure = retail distributing ──
    total_book = df["bid_volume"].fillna(0) + df["offer_volume"].fillna(0) + eps
    df["retail_sell_share"] = np.clip(
        df["offer_volume"].fillna(0) / total_book, 0.0, 1.0
    )

    # ── Absorption ratio: foreign buying vs sell-side offers ──
    # offer_volume is in lots (100 shares each); foreign_buy is in shares
    lot_size = 100
    df["absorption_ratio"] = df["foreign_buy"].fillna(0) / (
        df["offer_volume"].fillna(0) * lot_size + eps
    )
    df["absorption_ratio_norm"] = np.clip(df["absorption_ratio"] / 3.0, 0.0, 1.0)

    # ── Net flow (foreign net in shares, rolling windows) ──
    # Q3 default: compute but treat as informational (not in broker_flow_score sum)
    g = df.groupby("ticker", sort=False)
    for n in [1, 3, 5, 10]:
        df[f"net_flow_{n}d"] = g["foreign_net"].transform(
            lambda s, w=n: s.rolling(w, min_periods=1).sum()
        )

    # ── Accumulation streak: consecutive trailing days with foreign_net > 0 ──
    def _accum_streak(series: pd.Series) -> pd.Series:
        streak = pd.Series(0, index=series.index, dtype=int)
        current = 0
        for i, v in enumerate(series):
            current = current + 1 if v > 0 else 0
            streak.iloc[i] = current
        return streak

    df["accum_streak"] = g["foreign_net"].transform(_accum_streak)
    df["accum_streak"] = df["accum_streak"].clip(upper=10)
    df["accum_streak_norm"] = df["accum_streak"] / 10.0

    # ── Fragmentation proxy: high-volume + strong close = concentrated buying ──
    avg_vol_20d = g["volume"].transform(
        lambda s: s.rolling(20, min_periods=1).mean()
    )
    volume_ratio = df["volume"] / (avg_vol_20d + eps)
    close_position = (df["close"] - df["low"]) / (
        (df["high"] - df["low"]).replace(0, np.nan).fillna(eps)
    )
    df["fragmentation_norm"] = np.where(
        (volume_ratio > 1.3) & (close_position > 0.6), 1.0, 0.0
    )

    # ── broker_flow_score (0–100) ──
    latest = df.groupby("ticker").last().reset_index()

    raw = (
        latest["retail_sell_share"] * 30
        + latest["absorption_ratio_norm"] * 25
        + latest["accum_streak_norm"] * 25
        + latest["fragmentation_norm"] * 20
    )
    latest["broker_flow_score"] = np.clip(raw, 0.0, 100.0)

    cols = [
        "ticker",
        "retail_sell_share", "absorption_ratio_norm",
        "accum_streak", "accum_streak_norm",
        "fragmentation_norm",
        "net_flow_1d", "net_flow_3d", "net_flow_5d", "net_flow_10d",
        "broker_flow_score",
    ]
    return latest[cols].set_index("ticker")
