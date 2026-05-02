from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

LOT_SIZE = 100  # IDX: 1 lot = 100 shares


def _float_tightness(free_float_pct_100: float) -> float:
    """Map free-float % (0–100) to a tightness score (0–1)."""
    if free_float_pct_100 < 10:
        return 1.00
    if free_float_pct_100 < 20:
        return 0.85
    if free_float_pct_100 < 35:
        return 0.70
    if free_float_pct_100 < 50:
        return 0.50
    return 0.30


def compute(
    stock_df: pd.DataFrame,
    freefloat_df: pd.DataFrame,
    lookback: int = 20,
) -> pd.DataFrame:
    """
    Compute float-pressure features per ticker.

    Parameters
    ----------
    stock_df : DataFrame with [ticker, date, volume, foreign_buy, listed_shares]
               sorted by ticker, date ascending.
               listed_shares comes from stock_summary directly.
    freefloat_df : DataFrame with [ticker, free_float_pct] (0.0–1.0 fraction).
    lookback : rolling window for volume calculations

    Returns
    -------
    DataFrame indexed by ticker with:
        free_float_pct, effective_float_shares, turnover_to_float_norm,
        accum_to_float_norm, float_tightness, float_pressure_score
    """
    df = stock_df.copy().sort_values(["ticker", "date"])
    eps = 1e-9

    # ── Merge free-float percentages ──────────────────────────────────────
    ff = freefloat_df[["ticker", "free_float_pct"]].copy()
    df = df.merge(ff, on="ticker", how="left")

    # ── Use listed_shares from stock_summary ──────────────────────────────
    # Take the latest listed_shares value per ticker
    # (it changes rarely, but we use the most recent)

    g = df.groupby("ticker", sort=False)

    df["turnover_20d"] = g["volume"].transform(
        lambda s: s.rolling(lookback, min_periods=1).sum()
    )

    # Absorbed volume proxy: positive foreign_net as institutional accumulation
    # foreign_buy is in shares; sum over 5 days
    df["absorbed_5d_shares"] = g["foreign_buy"].transform(
        lambda s: s.rolling(5, min_periods=1).sum()
    ).fillna(0)

    # ── Take latest row per ticker ─────────────────────────────────────────
    latest = df.groupby("ticker").last().reset_index()

    # listed_shares from the database; free_float_pct from CSV (may be None)
    has_listed = (
        latest["listed_shares"].notna() & (latest["listed_shares"] > 0)
    )
    has_float = latest["free_float_pct"].notna()

    # Tickers missing either → float_pressure_score = 0
    missing_float = ~(has_listed & has_float)
    if missing_float.sum() > 0:
        logger.warning(
            "Float pressure disabled for %d tickers (missing listed_shares or free_float_pct)",
            missing_float.sum(),
        )

    latest["effective_float_shares"] = np.where(
        has_listed & has_float,
        latest["listed_shares"] * latest["free_float_pct"],
        np.nan,
    )

    eff_float = latest["effective_float_shares"].fillna(eps)

    # Turnover-to-float ratio (20-day volume / effective float shares)
    # volume is in shares (IDX stock_summary volume = shares traded)
    # Note: if volume is stored in lots, multiply by LOT_SIZE. We check: for BBCA
    # with 24B listed shares, a daily volume of ~100M shares is expected.
    # IDX-API stores volume in shares, so no conversion needed here.
    turnover_to_float = latest["turnover_20d"] / eff_float
    latest["turnover_to_float_norm"] = np.clip(turnover_to_float / 2.0, 0.0, 1.0)

    # Accumulation-to-float ratio (5-day institutional buy in shares / effective float)
    accum_to_float = latest["absorbed_5d_shares"] / eff_float
    latest["accum_to_float_norm"] = np.clip(accum_to_float / 0.05, 0.0, 1.0)

    # Float tightness (static)
    latest["float_tightness"] = latest.apply(
        lambda r: _float_tightness(r["free_float_pct"] * 100)
        if pd.notna(r["free_float_pct"])
        else 0.0,
        axis=1,
    )

    # Assemble score; zero out tickers with missing data
    raw = (
        latest["turnover_to_float_norm"] * 35
        + latest["accum_to_float_norm"] * 40
        + latest["float_tightness"] * 25
    )
    latest["float_pressure_score"] = np.where(
        missing_float, 0.0, np.clip(raw, 0.0, 100.0)
    )

    return latest[
        [
            "ticker", "free_float_pct", "effective_float_shares",
            "turnover_to_float_norm", "accum_to_float_norm",
            "float_tightness", "float_pressure_score",
        ]
    ].set_index("ticker")
