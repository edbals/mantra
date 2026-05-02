from __future__ import annotations

import numpy as np
import pandas as pd


def compute(
    stock_df: pd.DataFrame,
    ihsg_df: pd.DataFrame,
    lookback: int = 20,
) -> pd.DataFrame:
    """
    Compute price/volume structure features per ticker.

    Parameters
    ----------
    stock_df : DataFrame with [ticker, date, open, high, low, close, volume]
               sorted by ticker, date ascending.
    ihsg_df  : DataFrame with [date, close] for IHSG only, sorted by date.
    lookback : rolling window (default 20 trading days)

    Returns
    -------
    DataFrame indexed by ticker with:
        ma20, ma50, above_ma20, above_ma50, range_compression,
        volume_ratio, volume_ratio_norm, close_position,
        rs_vs_index_norm, structure_score
    """
    df = stock_df.copy().sort_values(["ticker", "date"])
    eps = 1e-9

    g = df.groupby("ticker", sort=False)

    # ── Moving averages ───────────────────────────────────────────────────
    df["ma20"] = g["close"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    df["ma50"] = g["close"].transform(lambda s: s.rolling(50, min_periods=1).mean())
    df["above_ma20"] = (df["close"] > df["ma20"]).astype(float)
    df["above_ma50"] = (df["close"] > df["ma50"]).astype(float)

    # ── Range compression ─────────────────────────────────────────────────
    df["daily_range"] = df["high"] - df["low"]
    df["atr_5d"] = g["daily_range"].transform(lambda s: s.rolling(5, min_periods=1).mean())
    df["atr_20d"] = g["daily_range"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    df["range_compression"] = 1.0 - np.minimum(
        df["atr_5d"] / (df["atr_20d"] + eps), 1.0
    )

    # ── Volume expansion ──────────────────────────────────────────────────
    df["avg_volume_20d"] = g["volume"].transform(
        lambda s: s.rolling(20, min_periods=1).mean()
    )
    df["volume_ratio"] = df["volume"] / (df["avg_volume_20d"] + eps)
    df["volume_ratio_norm"] = np.clip(df["volume_ratio"] / 5.0, 0.0, 1.0)

    # ── Close position in daily range ─────────────────────────────────────
    df["close_position"] = (df["close"] - df["low"]) / (
        (df["high"] - df["low"]).replace(0, np.nan).fillna(eps)
    )
    df["close_position"] = np.clip(df["close_position"], 0.0, 1.0)

    # ── Relative strength vs IHSG (20-day) ───────────────────────────────
    # IHSG: filter for the composite index (name contains 'COMPOSITE' or 'IDX')
    ihsg = ihsg_df[
        ihsg_df["index_name"].str.upper().str.contains("COMPOSITE|IHSG|IDX", na=False)
    ].sort_values("date").copy()

    if ihsg.empty:
        # Fallback: use the first available index if IHSG name is different
        ihsg = ihsg_df.sort_values("date").copy()

    ihsg = ihsg.set_index("date")["close"].rename("ihsg_close")

    # Merge IHSG into the per-ticker data
    df = df.merge(ihsg.reset_index(), on="date", how="left")
    df["ihsg_close"] = df["ihsg_close"].ffill()

    # 20-day percentage return per ticker and for IHSG
    def _pct_change_20(s: pd.Series) -> pd.Series:
        shifted = s.shift(20)
        return (s - shifted) / (shifted.abs() + eps)

    df["ticker_pct_20d"] = g["close"].transform(_pct_change_20)

    # IHSG 20-day return (same date for all tickers)
    ihsg_pct = ihsg.pct_change(20).rename("ihsg_pct_20d")
    df = df.merge(ihsg_pct.reset_index().rename(columns={"close": "ihsg_pct_20d"}), on="date", how="left")
    df["ihsg_pct_20d"] = df["ihsg_pct_20d"].ffill().fillna(0)

    df["rs_vs_index"] = df["ticker_pct_20d"].fillna(0) - df["ihsg_pct_20d"]
    # Normalize: clamp to [-0.3, 0.3], shift to [0, 0.6], divide by 0.6
    df["rs_vs_index_norm"] = (
        np.clip(df["rs_vs_index"], -0.3, 0.3) + 0.3
    ) / 0.6

    # ── structure_score (0–100) ───────────────────────────────────────────
    raw = (
        df["above_ma20"] * 15
        + df["above_ma50"] * 15
        + df["range_compression"] * 25
        + df["volume_ratio_norm"] * 25
        + df["close_position"] * 10
        + df["rs_vs_index_norm"] * 10
    )
    df["structure_score"] = np.clip(raw, 0.0, 100.0)

    # Take latest row per ticker
    latest = df.groupby("ticker").last().reset_index()

    return latest[
        [
            "ticker", "ma20", "ma50",
            "above_ma20", "above_ma50",
            "range_compression", "volume_ratio", "volume_ratio_norm",
            "close_position", "rs_vs_index_norm", "structure_score",
        ]
    ].set_index("ticker")
