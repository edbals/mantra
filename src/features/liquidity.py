from __future__ import annotations

import numpy as np
import pandas as pd


def _liquidity_tier(avg_value: float) -> float:
    """Map average daily IDR value to a 0–1 tier score."""
    if avg_value >= 10_000_000_000:   # > 10B
        return 1.00
    if avg_value >= 1_000_000_000:    # 1B–10B
        return 0.75
    if avg_value >= 500_000_000:      # 500M–1B
        return 0.50
    if avg_value >= 100_000_000:      # 100M–500M
        return 0.25
    return 0.00                        # < 100M


def compute(stock_df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    Compute liquidity features per ticker for the most recent date.

    Parameters
    ----------
    stock_df : DataFrame with columns [ticker, date, close, high, low, value, volume]
               sorted by ticker, date ascending.
    lookback : rolling window in trading days (default 20)

    Returns
    -------
    DataFrame indexed by ticker with columns:
        avg_daily_value_idr, median_spread_proxy, liquidity_tier,
        spread_norm, liquidity_score
    """
    df = stock_df.copy().sort_values(["ticker", "date"])

    g = df.groupby("ticker", sort=False)

    # rolling mean over last `lookback` rows per ticker
    df["avg_daily_value_idr"] = g["value"].transform(
        lambda s: s.rolling(lookback, min_periods=1).mean()
    )
    df["spread_proxy"] = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
    df["median_spread_proxy"] = g["spread_proxy"].transform(
        lambda s: s.rolling(lookback, min_periods=1).mean()
    )

    # Take latest row per ticker only
    latest = df.groupby("ticker").last().reset_index()

    latest["liquidity_tier"] = latest["avg_daily_value_idr"].apply(_liquidity_tier)
    latest["spread_norm"] = (
        1.0 - np.minimum(latest["median_spread_proxy"].fillna(0.05) / 0.05, 1.0)
    )
    raw_score = latest["liquidity_tier"] * 70 + latest["spread_norm"] * 30
    latest["liquidity_score"] = np.clip(raw_score, 0, 100)

    return latest[
        ["ticker", "avg_daily_value_idr", "median_spread_proxy",
         "liquidity_tier", "spread_norm", "liquidity_score"]
    ].set_index("ticker")
