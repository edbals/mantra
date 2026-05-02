"""Unit tests for feature modules using mock DataFrames."""

import numpy as np
import pandas as pd
import pytest

from src.features import liquidity, broker_flow, float_pressure, structure, catalyst


# ── Shared helpers ────────────────────────────────────────────────────────────

def make_stock_df(n_days=25, n_tickers=2, seed=42):
    """Minimal stock_summary mock."""
    rng = np.random.default_rng(seed)
    records = []
    dates = pd.date_range("2025-01-01", periods=n_days, freq="B")
    for t in [f"TICK{i}" for i in range(n_tickers)]:
        close = 1000.0
        for d in dates:
            close = close * (1 + rng.normal(0, 0.01))
            high = close * (1 + abs(rng.normal(0, 0.005)))
            low = close * (1 - abs(rng.normal(0, 0.005)))
            vol = int(rng.integers(1_000_000, 10_000_000))
            records.append({
                "ticker": t, "date": d,
                "open": close * 0.999, "high": high, "low": low, "close": close,
                "volume": vol, "value": vol * close,
                "bid_volume": int(rng.integers(100, 1000)),
                "offer_volume": int(rng.integers(100, 1000)),
                "foreign_buy": int(rng.integers(0, 500_000)),
                "foreign_sell": int(rng.integers(0, 500_000)),
                "foreign_net": int(rng.integers(-200_000, 200_000)),
                "listed_shares": 10_000_000_000,
            })
    return pd.DataFrame(records)


# ── Liquidity ─────────────────────────────────────────────────────────────────

def test_liquidity_score_range():
    df = make_stock_df()
    result = liquidity.compute(df)
    assert set(result.columns) >= {"liquidity_score", "avg_daily_value_idr"}
    assert (result["liquidity_score"] >= 0).all()
    assert (result["liquidity_score"] <= 100).all()


def test_liquidity_highly_liquid():
    """A ticker trading 20B IDR/day should get liquidity_tier = 1.0 → score ≥ 70."""
    df = make_stock_df(n_tickers=1)
    df["value"] = 20_000_000_000  # force high liquidity
    result = liquidity.compute(df)
    assert result["liquidity_score"].iloc[0] >= 70


def test_liquidity_illiquid():
    """A ticker trading 50M IDR/day should get liquidity_tier = 0 → score < 30."""
    df = make_stock_df(n_tickers=1)
    df["value"] = 50_000_000  # below 100M threshold
    result = liquidity.compute(df)
    assert result["liquidity_score"].iloc[0] < 30


# ── Broker Flow ───────────────────────────────────────────────────────────────

def test_broker_flow_score_range():
    df = make_stock_df()
    result = broker_flow.compute(df)
    assert (result["broker_flow_score"] >= 0).all()
    assert (result["broker_flow_score"] <= 100).all()


def test_broker_flow_all_foreign_net_positive():
    """All foreign_net > 0 for 10+ days → accum_streak_norm = 1.0 → contributes 25 pts."""
    df = make_stock_df(n_days=25, n_tickers=1)
    df["foreign_net"] = 500_000  # always positive
    result = broker_flow.compute(df)
    assert result["accum_streak_norm"].iloc[0] == pytest.approx(1.0)
    assert result["broker_flow_score"].iloc[0] >= 25


def test_broker_flow_informational_columns_present():
    """net_flow_Nd columns must exist (Q3 default)."""
    df = make_stock_df()
    result = broker_flow.compute(df)
    for n in [1, 3, 5, 10]:
        assert f"net_flow_{n}d" in result.columns


# ── Float Pressure ────────────────────────────────────────────────────────────

def test_float_pressure_missing_freefloat():
    """Tickers not in freefloat CSV get float_pressure_score = 0."""
    df = make_stock_df(n_tickers=1)
    empty_ff = pd.DataFrame(columns=["ticker", "free_float_pct"])
    result = float_pressure.compute(df, empty_ff)
    assert result["float_pressure_score"].iloc[0] == 0.0


def test_float_pressure_tight_float():
    """Float < 10% → tightness = 1.0 → contributes 25 pts to score."""
    df = make_stock_df(n_tickers=1)
    ticker = df["ticker"].iloc[0]
    ff = pd.DataFrame({"ticker": [ticker], "free_float_pct": [0.08]})  # 8%
    result = float_pressure.compute(df, ff)
    assert result["float_tightness"].iloc[0] == pytest.approx(1.0)
    assert result["float_pressure_score"].iloc[0] >= 25


def test_float_pressure_score_range():
    df = make_stock_df()
    tickers = df["ticker"].unique()
    ff = pd.DataFrame({"ticker": list(tickers), "free_float_pct": [0.30, 0.15]})
    result = float_pressure.compute(df, ff)
    assert (result["float_pressure_score"] >= 0).all()
    assert (result["float_pressure_score"] <= 100).all()


# ── Structure ─────────────────────────────────────────────────────────────────

def make_ihsg_df(n_days=60):
    dates = pd.date_range("2024-11-01", periods=n_days, freq="B")
    closes = 7000 + np.cumsum(np.random.randn(n_days) * 20)
    return pd.DataFrame({"date": dates, "index_name": "IDX COMPOSITE", "close": closes})


def test_structure_score_range():
    df = make_stock_df()
    ihsg = make_ihsg_df()
    result = structure.compute(df, ihsg)
    assert (result["structure_score"] >= 0).all()
    assert (result["structure_score"] <= 100).all()


def test_structure_above_ma20():
    """Ticker consistently rising above MA20 → above_ma20 = 1."""
    df = make_stock_df(n_tickers=1)
    # Force rising price
    df = df.sort_values("date").copy()
    df["close"] = range(1000, 1000 + len(df))
    df["high"] = df["close"] + 5
    df["low"] = df["close"] - 5
    ihsg = make_ihsg_df()
    result = structure.compute(df, ihsg)
    assert result["above_ma20"].iloc[0] == 1.0


# ── Catalyst ──────────────────────────────────────────────────────────────────

def test_catalyst_all_zeros_with_empty_inputs():
    scoring_date = pd.Timestamp("2025-03-01")
    tickers = ["TICK0", "TICK1"]
    df = make_stock_df()
    result = catalyst.compute(
        scoring_date, tickers,
        pd.DataFrame(columns=["ticker", "cum_date"]),
        pd.DataFrame(columns=["ticker", "exercise_date"]),
        pd.DataFrame(columns=["ticker", "split_date"]),
        pd.DataFrame(columns=["ticker", "date", "title"]),
        pd.DataFrame(columns=["ticker", "date", "type"]),
        df,
    )
    assert (result["catalyst_score"] >= 0).all()
    assert (result["catalyst_score"] <= 100).all()


def test_catalyst_suspension_penalty():
    """Suspended ticker should get suspension_penalty = -1 → max(0, …) clamps to 0."""
    scoring_date = pd.Timestamp("2025-03-01")
    tickers = ["BBCA"]
    df = make_stock_df(n_tickers=1)
    df["ticker"] = "BBCA"
    suspensions = pd.DataFrame({
        "ticker": ["BBCA"],
        "date": [pd.Timestamp("2025-02-28")],
        "type": ["Suspend"],
    })
    result = catalyst.compute(
        scoring_date, tickers,
        pd.DataFrame(columns=["ticker", "cum_date"]),
        pd.DataFrame(columns=["ticker", "exercise_date"]),
        pd.DataFrame(columns=["ticker", "split_date"]),
        pd.DataFrame(columns=["ticker", "date", "title"]),
        suspensions,
        df,
    )
    assert result.loc["BBCA", "catalyst_score"] == 0.0


def test_catalyst_dividend_signal():
    """Upcoming dividend within 30 days → has_div_soon = 1 → at least 35 pts."""
    scoring_date = pd.Timestamp("2025-03-01")
    tickers = ["BBCA"]
    df = make_stock_df(n_tickers=1)
    df["ticker"] = "BBCA"
    divs = pd.DataFrame({"ticker": ["BBCA"], "cum_date": [scoring_date + pd.Timedelta(days=10)]})
    result = catalyst.compute(
        scoring_date, tickers,
        divs,
        pd.DataFrame(columns=["ticker", "exercise_date"]),
        pd.DataFrame(columns=["ticker", "split_date"]),
        pd.DataFrame(columns=["ticker", "date", "title"]),
        pd.DataFrame(columns=["ticker", "date", "type"]),
        df,
    )
    assert result.loc["BBCA", "has_div_soon"] == 1
    assert result.loc["BBCA", "catalyst_score"] >= 35


# ── Scoring decision logic ────────────────────────────────────────────────────

def test_get_action_labels():
    from src.config import Config
    from src.scoring import get_action
    cfg = Config.load()

    assert get_action(85, 75, 5_000_000_000, cfg) == "INVEST"
    assert get_action(85, 60, 5_000_000_000, cfg) == "WATCH_EXEC"
    assert get_action(70, 80, 5_000_000_000, cfg) == "WATCH"
    assert get_action(55, 50, 5_000_000_000, cfg) == "OBSERVE"
    assert get_action(30, 30, 5_000_000_000, cfg) == "AVOID"
    assert get_action(85, 75, 100_000_000, cfg) == "ILLIQUID"  # below min
