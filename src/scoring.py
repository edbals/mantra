from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import Config


def compute_investment_score(
    tickers: pd.Index,
    broker_flow: pd.DataFrame,
    float_pressure: pd.DataFrame,
    structure: pd.DataFrame,
    liquidity: pd.DataFrame,
    catalyst: pd.DataFrame,
    weights,
) -> pd.DataFrame:
    """Combine sub-scores into a single investment_score per ticker."""
    out = pd.DataFrame(index=tickers)

    def _get(df: pd.DataFrame, col: str) -> pd.Series:
        if col in df.columns:
            return df[col].reindex(tickers).fillna(0)
        return pd.Series(0.0, index=tickers)

    out["broker_flow_score"]    = _get(broker_flow, "broker_flow_score")
    out["float_pressure_score"] = _get(float_pressure, "float_pressure_score")
    out["structure_score"]      = _get(structure, "structure_score")
    out["liquidity_score"]      = _get(liquidity, "liquidity_score")
    out["catalyst_score"]       = _get(catalyst, "catalyst_score")

    out["investment_score"] = np.clip(
        weights.broker_flow    * out["broker_flow_score"]
        + weights.float_pressure * out["float_pressure_score"]
        + weights.structure      * out["structure_score"]
        + weights.liquidity      * out["liquidity_score"]
        + weights.catalyst       * out["catalyst_score"],
        0.0, 100.0,
    )
    return out


def compute_breakout_signal(stock_df: pd.DataFrame) -> pd.DataFrame:
    """
    Replaces the full execution score with a single boolean breakout_signal.

    True when ALL of:
      - close >= 98% of the 20-day rolling high  (near or at breakout)
      - close > MA20                              (above trend)
      - volume > 1.3x 20-day average volume      (volume confirmation)

    Also retains volume_ratio, ma20, close_pos as informational columns.
    """
    df = stock_df.copy().sort_values(["ticker", "date"])
    eps = 1e-9
    g   = df.groupby("ticker", sort=False)

    df["ma20"]           = g["close"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    df["pivot_high_20d"] = g["high"].transform(lambda s: s.rolling(20, min_periods=1).max())
    df["avg_volume_20d"] = g["volume"].transform(lambda s: s.rolling(20, min_periods=1).mean())
    df["volume_ratio"]   = df["volume"] / (df["avg_volume_20d"] + eps)
    df["close_pos"]      = (df["close"] - df["low"]) / (
        (df["high"] - df["low"]).replace(0, np.nan).fillna(eps)
    )

    df["breakout_signal"] = (
        (df["close"] >= df["pivot_high_20d"] * 0.98)
        & (df["close"] > df["ma20"])
        & (df["volume_ratio"] > 1.3)
    )

    latest = df.groupby("ticker").last().reset_index()
    return latest[["ticker", "breakout_signal", "volume_ratio", "close_pos", "ma20"]].set_index("ticker")


def get_action(
    investment_score: float,
    avg_daily_value_idr: float,
    breakout_signal: bool,
    suspended: bool,
    cfg: Config,
) -> str:
    if suspended:
        return "AVOID"
    if avg_daily_value_idr < cfg.min_avg_daily_value_idr:
        return "ILLIQUID"
    t = cfg.thresholds
    if investment_score >= t.invest and breakout_signal:
        return "INVEST"
    if investment_score >= t.invest and not breakout_signal:
        return "WATCH_EXEC"
    if investment_score >= t.watch:
        return "WATCH"
    if investment_score >= t.observe:
        return "OBSERVE"
    return "AVOID"


def apply_decision_labels(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    df["action"] = [
        get_action(
            row["investment_score"],
            row["avg_daily_value_idr"],
            bool(row.get("breakout_signal", False)),
            bool(row.get("suspension_flag", 0)),
            cfg,
        )
        for _, row in df.iterrows()
    ]
    return df
