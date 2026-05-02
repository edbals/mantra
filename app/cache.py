"""Streamlit cache wrappers around engine.py calls and IDX-API direct queries."""

from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from src.config import Config
from src.engine import list_available_dates, get_ticker_history  # noqa: F401
from src.db import ScoresDB
from src.indexalpha import IndexAlphaClient


@st.cache_data(ttl=3600)
def cached_available_dates(config_path: str) -> list[str]:
    cfg = Config.load(config_path)
    return list_available_dates(cfg)


@st.cache_data(ttl=3600)
def cached_scores_for_date(date: str, config_path: str) -> pd.DataFrame:
    """Load scores — tries CSV first (has more columns), falls back to DB."""
    cfg = Config.load(config_path)
    csv_path = cfg.output_dir / f"scores_{date}.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        return df.sort_values("investment_score", ascending=False).reset_index(drop=True)
    db = ScoresDB(cfg.output_dir / "scores.db")
    df = pd.read_sql_query(
        "SELECT * FROM scores_daily WHERE date = ? ORDER BY investment_score DESC",
        db._con,
        params=(date,),
    )
    db.close()
    return df


@st.cache_data(ttl=3600)
def cached_ticker_history(ticker: str, config_path: str, days: int = 60) -> pd.DataFrame:
    cfg = Config.load(config_path)
    return get_ticker_history(ticker, cfg, days)


@st.cache_data(ttl=3600)
def cached_ticker_flow(ticker: str, config_path: str, days: int = 30) -> pd.DataFrame:
    """
    Load per-ticker OHLCV + foreign buy/sell/net + bid/offer volumes from IDX-API.
    Returns up to `days` most recent trading days, sorted newest-first.
    """
    cfg = Config.load(config_path)
    if not cfg.idxdb_path.exists():
        return pd.DataFrame()

    con = sqlite3.connect(str(cfg.idxdb_path), check_same_thread=False)
    cutoff_ms = int(
        (pd.Timestamp.now() - pd.Timedelta(days=days * 3)).timestamp() * 1000
    )
    try:
        df = pd.read_sql_query(
            """
            SELECT date AS date_ms,
                   open, high, low, close, volume, value,
                   foreign_buy, foreign_sell, foreign_net,
                   bid_volume, offer_volume
            FROM stock_summary
            WHERE code = ?
              AND date >= ?
              AND close IS NOT NULL
              AND volume > 0
            ORDER BY date DESC
            LIMIT ?
            """,
            con,
            params=(ticker, cutoff_ms, days),
        )
    finally:
        con.close()

    if df.empty:
        return df

    df["date"] = (
        pd.to_datetime(df["date_ms"], unit="ms", utc=True)
        .dt.tz_convert(None)
        .dt.date
    )
    return df.drop(columns=["date_ms"])


@st.cache_data(ttl=86400)
def cached_broker_summary(
    ticker: str,
    date: str,
    investor: str,
    config_path: str,
) -> tuple[pd.DataFrame, str]:
    """
    Fetch broker distribution for ticker+date from Index Alpha API.
    Returns (DataFrame, error_message). error_message is "" on success.
    Results are cached locally in scores.db (never re-fetched for same date).
    """
    cfg = Config.load(config_path)
    client = IndexAlphaClient(
        api_key=cfg.indexalpha_api_key,
        db_path=cfg.output_dir / "scores.db",
    )
    try:
        df = client.get_broker_summary(ticker, date, investor)
        return df, ""
    except Exception as exc:
        return pd.DataFrame(), str(exc)


@st.cache_data(ttl=3600)
def cached_broker_history(
    ticker: str,
    dates: tuple,
    investor: str,
    config_path: str,
) -> pd.DataFrame:
    """
    Fetch broker data for multiple dates and return a long DataFrame.
    `dates` must be a tuple (not list) so Streamlit can hash it.
    """
    cfg = Config.load(config_path)
    client = IndexAlphaClient(
        api_key=cfg.indexalpha_api_key,
        db_path=cfg.output_dir / "scores.db",
    )
    return client.get_broker_history(ticker, list(dates), investor)


@st.cache_data(ttl=3600)
def cached_broker_names(config_path: str) -> dict[str, str]:
    """Load broker code → name mapping from IDX-API participant_broker table."""
    cfg = Config.load(config_path)
    if not cfg.idxdb_path.exists():
        return {}
    con = sqlite3.connect(str(cfg.idxdb_path), check_same_thread=False)
    try:
        df = pd.read_sql_query("SELECT code, name FROM participant_broker", con)
    finally:
        con.close()
    return dict(zip(df["code"], df["name"]))
