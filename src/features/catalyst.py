from __future__ import annotations

import numpy as np
import pandas as pd


def compute(
    scoring_date: pd.Timestamp,
    tickers: list[str],
    dividends_df: pd.DataFrame,
    rights_df: pd.DataFrame,
    splits_df: pd.DataFrame,
    announcements_df: pd.DataFrame,
    suspensions_df: pd.DataFrame,
    stock_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute catalyst features per ticker.

    Parameters
    ----------
    scoring_date      : The date being scored.
    tickers           : List of all tickers to score.
    dividends_df      : [ticker, cum_date] — cum-dividend dates
    rights_df         : [ticker, exercise_date]
    splits_df         : [ticker, split_date]
    announcements_df  : [ticker, date, title]
    suspensions_df    : [ticker, date, type] — type = 'Suspend' or 'Unsuspend'
    stock_df          : Full stock history with [ticker, date, foreign_net]

    Returns
    -------
    DataFrame indexed by ticker with:
        has_div_soon, has_rights_soon, has_split_soon,
        has_recent_announcement, foreign_signal, suspension_penalty,
        catalyst_score
    """
    result = pd.DataFrame({"ticker": tickers}).set_index("ticker")
    result["has_div_soon"] = 0
    result["has_rights_soon"] = 0
    result["has_split_soon"] = 0
    result["has_recent_announcement"] = 0
    result["foreign_signal"] = 0
    result["suspension_penalty"] = 0

    # ── Dividend within 30 days ───────────────────────────────────────────
    if not dividends_df.empty:
        horizon = scoring_date + pd.Timedelta(days=30)
        div_tickers = dividends_df[
            (dividends_df["cum_date"] >= scoring_date)
            & (dividends_df["cum_date"] <= horizon)
        ]["ticker"].unique()
        result.loc[result.index.isin(div_tickers), "has_div_soon"] = 1

    # ── Rights offering within 60 days ───────────────────────────────────
    if not rights_df.empty:
        horizon = scoring_date + pd.Timedelta(days=60)
        rights_tickers = rights_df[
            (rights_df["exercise_date"] >= scoring_date)
            & (rights_df["exercise_date"] <= horizon)
        ]["ticker"].unique()
        result.loc[result.index.isin(rights_tickers), "has_rights_soon"] = 1

    # ── Stock split within 30 days ────────────────────────────────────────
    if not splits_df.empty:
        horizon = scoring_date + pd.Timedelta(days=30)
        split_tickers = splits_df[
            (splits_df["split_date"] >= scoring_date)
            & (splits_df["split_date"] <= horizon)
        ]["ticker"].unique()
        result.loc[result.index.isin(split_tickers), "has_split_soon"] = 1

    # ── Recent announcement within 7 days ────────────────────────────────
    if not announcements_df.empty:
        cutoff = scoring_date - pd.Timedelta(days=7)
        ann_tickers = announcements_df[
            announcements_df["date"] >= cutoff
        ]["ticker"].unique()
        result.loc[result.index.isin(ann_tickers), "has_recent_announcement"] = 1

    # ── Foreign flow signal (5-day net from stock_summary) ───────────────
    if not stock_df.empty and "foreign_net" in stock_df.columns:
        fdf = stock_df.sort_values(["ticker", "date"])
        fdf_5d = (
            fdf.groupby("ticker")["foreign_net"]
            .apply(lambda s: s.tail(5).sum())
            .reset_index()
            .rename(columns={"foreign_net": "foreign_net_5d"})
        )
        fdf_5d["foreign_signal"] = (fdf_5d["foreign_net_5d"] > 0).astype(int)
        fdf_5d = fdf_5d.set_index("ticker")
        result["foreign_signal"] = fdf_5d["foreign_signal"].reindex(result.index).fillna(0)

    # ── Suspension risk: -1 if most recent event for ticker is 'Suspend' ─
    # Q2 default: penalty * 50 = -50 pts deducted
    if not suspensions_df.empty:
        latest_suspend = (
            suspensions_df.sort_values("date")
            .groupby("ticker")
            .last()
            .reset_index()[["ticker", "type"]]
        )
        suspended_tickers = latest_suspend[
            latest_suspend["type"].str.lower() == "suspend"
        ]["ticker"].unique()
        result.loc[result.index.isin(suspended_tickers), "suspension_penalty"] = -1

    # suspension_flag: hard AVOID override in scoring — no -50 bleed into catalyst_score
    result["suspension_flag"] = (result["suspension_penalty"] < 0).astype(int)

    # catalyst_score (0–100) — informational only, not part of investment_score
    raw = (
        result["has_div_soon"] * 35
        + result["has_rights_soon"] * 20
        + result["has_split_soon"] * 25
        + result["has_recent_announcement"] * 10
        + result["foreign_signal"] * 10
    )
    result["catalyst_score"] = np.clip(raw, 0.0, 100.0)

    return result
