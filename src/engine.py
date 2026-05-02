from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import Config
from src.loader import IDXLoader
from src.db import ScoresDB
from src import features
from src.features import broker_flow, broker_flow_real, float_pressure, structure, liquidity, catalyst
from src.indexalpha import IndexAlphaClient
from src.scoring import (
    compute_investment_score,
    compute_breakout_signal,
    apply_decision_labels,
)
from src import output as out_mod

logger = logging.getLogger(__name__)


@dataclass
class ScoringResult:
    ranked_df: pd.DataFrame
    summary_dict: dict
    scoring_date: str
    total_screened: int
    runtime_seconds: float
    skipped: list[str] = field(default_factory=list)


STAGE2_TOP_N = 100


def _stage2_real_broker_flow(master: pd.DataFrame, scoring_date: str, cfg: Config) -> pd.DataFrame:
    """
    Re-score the top STAGE2_TOP_N tickers using real Index Alpha broker data.

    Stage-1 rank key (Mantra 2.2):
        stage1_rank_key = float_pressure_score * 0.6 + (100 - liquidity_score) * 0.4
    Prefers high float pressure + lower liquidity (more price-sensitive names).
    """
    if not cfg.indexalpha_api_key or cfg.indexalpha_api_key.startswith("YOUR_"):
        logger.info("Stage 2 skipped: no Index Alpha API key configured")
        master["broker_data_source"] = "proxy"
        return master

    # ── Stage-1 rank key ──────────────────────────────────────────────────────
    master = master.copy()
    master["_stage1_key"] = (
        master.get("float_pressure_score", pd.Series(0.0, index=master.index)).fillna(0) * 0.6
        + (100.0 - master.get("liquidity_score", pd.Series(0.0, index=master.index)).fillna(0)) * 0.4
    )

    stage2_tickers = (
        master.sort_values("_stage1_key", ascending=False)
        .head(STAGE2_TOP_N)["ticker"]
        .tolist()
    )

    logger.info(
        "Stage 2: fetching real broker flow for %d tickers (top by FF x ADV blend)",
        len(stage2_tickers),
    )

    # ── Call Index Alpha ──────────────────────────────────────────────────────
    client = IndexAlphaClient(
        api_key=cfg.indexalpha_api_key,
        db_path=cfg.output_dir / "scores.db",
    )
    loader = IDXLoader(cfg)
    broker_master_df = loader.load_broker_master(cfg.broker_master_csv)
    loader.close()

    from_ts   = pd.Timestamp(scoring_date) - pd.Timedelta(days=30)
    from_date = str(from_ts.date())

    # Prefetch 20 trading days of per-day history so z-score works from day 1
    loader2 = IDXLoader(cfg)
    stock_snap = loader2.load_stock_summary(pd.Timestamp(scoring_date), 20)
    loader2.close()
    trading_dates = sorted(
        stock_snap[stock_snap["date"] <= pd.Timestamp(scoring_date)]["date"]
        .drop_duplicates()
        .apply(lambda d: str(d.date()) if hasattr(d, "date") else str(d))
        .tolist()
    )[-20:]
    fetched, skipped = client.prefetch_history(stage2_tickers, trading_dates)
    logger.info("History prefetch: %d new, %d cached", fetched, skipped)

    real_df = broker_flow_real.compute_real(
        tickers=stage2_tickers,
        scoring_date=scoring_date,
        from_date=from_date,
        client=client,
        broker_master_df=broker_master_df,
    )

    # ── Merge real scores alongside proxy — proxy score untouched ────────────
    # broker_flow_score (proxy) stays as-is.
    # Real data lands in separate columns: broker_flow_real_score, etc.
    real_cols = [
        "broker_data_source",
        "broker_flow_real_score",   # separate — does NOT overwrite broker_flow_score
        "inst_net_vol_today", "retail_net_vol_today",
        "retail_sell_share", "absorption_ratio", "absorption_ratio_norm",
        "accum_streak", "accum_streak_norm",
        "top_buyers", "top_sellers",
        "xl_xc_selling", "xl_xc_buying",
        "xl_xc_trend_days", "xl_xc_trend_selling",
        "sustained_buyers", "score_adj",
    ]

    # Rename broker_flow_score from real_df → broker_flow_real_score
    if "broker_flow_score" in real_df.columns:
        real_df = real_df.rename(columns={"broker_flow_score": "broker_flow_real_score"})

    master = master.set_index("ticker")
    real_rows = real_df[real_df.get("broker_data_source", pd.Series()) == "indexalpha"]
    for col in real_cols:
        if col in real_df.columns:
            master[col] = real_df[col].reindex(master.index)

    # Fill defaults for tickers not in Stage 2
    master["broker_data_source"]    = master["broker_data_source"].fillna("proxy")
    master["broker_flow_real_score"] = master.get("broker_flow_real_score", pd.Series(dtype=float)).where(
        master["broker_data_source"] == "indexalpha"
    )
    master["top_buyers"]          = master["top_buyers"].fillna("")
    master["top_sellers"]         = master["top_sellers"].fillna("")
    master["xl_xc_selling"]       = master["xl_xc_selling"].fillna(False)
    master["xl_xc_buying"]        = master["xl_xc_buying"].fillna(False)
    master["xl_xc_trend_days"]    = master["xl_xc_trend_days"].fillna(0).astype(int)
    master["xl_xc_trend_selling"] = master["xl_xc_trend_selling"].fillna(False)
    master["sustained_buyers"]    = master["sustained_buyers"].fillna("")

    # investment_score stays based on proxy broker_flow_score throughout
    master = master.reset_index()
    master = master.drop(columns=["_stage1_key"], errors="ignore")
    return master


def score_date(date: str | None, cfg: Config) -> ScoringResult:
    """
    Run the full scoring pipeline for a given date (or 'auto' for latest).
    Returns a ScoringResult with the ranked DataFrame and summary.
    """
    t0 = time.time()
    loader = IDXLoader(cfg)

    # ── Resolve date ──────────────────────────────────────────────────────
    scoring_ts = loader.resolve_scoring_date(cfg.scoring_date if date is None else date)
    date_str = str(scoring_ts.date())
    lookback = cfg.lookback_days

    # ── Load raw data ─────────────────────────────────────────────────────
    stock_df = loader.load_stock_summary(scoring_ts, lookback)
    ihsg_df = loader.load_daily_index(scoring_ts, lookback)
    freefloat_df = loader.load_freefloat_csv(cfg.freefloat_csv)
    dividends_df = loader.load_dividends(scoring_ts)
    rights_df = loader.load_right_offerings(scoring_ts)
    splits_df = loader.load_stock_splits(scoring_ts)
    announcements_df = loader.load_announcements(scoring_ts)
    suspensions_df = loader.load_suspensions()
    company_df = loader.load_company_profiles()
    loader.close()

    # ── Filter to tickers with enough trading days ────────────────────────
    trading_day_counts = (
        stock_df[stock_df["date"] <= scoring_ts]
        .groupby("ticker")["date"]
        .nunique()
    )
    eligible = trading_day_counts[
        trading_day_counts >= cfg.min_trading_days
    ].index.tolist()
    skipped_min_days = trading_day_counts[
        trading_day_counts < cfg.min_trading_days
    ].index.tolist()
    if skipped_min_days:
        logger.info(
            "Skipped %d tickers (< %d trading days): %s ...",
            len(skipped_min_days), cfg.min_trading_days,
            skipped_min_days[:5],
        )

    stock_df = stock_df[stock_df["ticker"].isin(eligible)]
    tickers = sorted(eligible)
    logger.info("Scoring %d tickers for %s", len(tickers), date_str)

    # ── Feature computation ───────────────────────────────────────────────
    lq = liquidity.compute(stock_df, lookback)
    bf = broker_flow.compute(stock_df, lookback)
    fp = float_pressure.compute(stock_df, freefloat_df, lookback)
    st = structure.compute(stock_df, ihsg_df, lookback)
    cat = catalyst.compute(
        scoring_ts, tickers,
        dividends_df, rights_df, splits_df,
        announcements_df, suspensions_df, stock_df,
    )
    exec_scores = compute_breakout_signal(stock_df)

    # ── Investment score ──────────────────────────────────────────────────
    inv = compute_investment_score(
        pd.Index(tickers, name="ticker"), bf, fp, st, lq, cat, cfg.weights
    )

    # ── Assemble master DataFrame ─────────────────────────────────────────
    master = inv.copy()
    for df_feat in [lq, bf, fp, st, cat, exec_scores]:
        for col in df_feat.columns:
            if col not in master.columns:
                master[col] = df_feat[col].reindex(master.index)

    master = master.reset_index()  # ticker becomes a column

    # Add close price and volume from latest stock data for CSV output
    latest_stock = (
        stock_df[stock_df["date"] == scoring_ts]
        .set_index("ticker")[["close", "volume"]]
    )
    master = master.merge(
        latest_stock.reset_index(), on="ticker", how="left"
    )

    # Add company names
    master = master.merge(company_df, on="ticker", how="left")
    master["company_name"] = master["company_name"].fillna(master["ticker"])

    # Add ff_category from freefloat CSV
    ff_cat = freefloat_df[["ticker", "ff_category"]] if "ff_category" in freefloat_df.columns else None
    if ff_cat is not None:
        master = master.merge(ff_cat, on="ticker", how="left")

    # Apply decision labels
    master = apply_decision_labels(master, cfg)

    # ── Stage 2: real broker flow for top tickers by FF x ADV blend ──────────
    master = _stage2_real_broker_flow(master, date_str, cfg)

    # ── Recompute investment_score using real broker flow where available ──────
    _FF_TREND_BOOST = {"LOW": 5.0, "MID": 3.0, "HIGH": 1.0}

    real_mask = master["broker_data_source"] == "indexalpha"
    if real_mask.any() and "broker_flow_real_score" in master.columns:
        w = cfg.weights
        real_bf = master.loc[real_mask, "broker_flow_real_score"].fillna(
            master.loc[real_mask, "broker_flow_score"]
        )
        base = (
            real_bf                                                          * w.broker_flow
            + master.loc[real_mask, "float_pressure_score"].fillna(0)       * w.float_pressure
            + master.loc[real_mask, "structure_score"].fillna(0)            * w.structure
            + master.loc[real_mask, "liquidity_score"].fillna(0)            * w.liquidity
            # catalyst excluded from investment_score (Mantra 2.2 — informational only)
        )

        # XL/XC trend boost — scaled by free float category × trend days
        trend_days = master.loc[real_mask, "xl_xc_trend_days"].fillna(0)
        ff_cat     = master.loc[real_mask, "ff_category"].fillna("HIGH")
        ff_max     = ff_cat.map(_FF_TREND_BOOST).fillna(0.0)
        trend_boost = ff_max * (trend_days / 10).clip(0, 1)

        master.loc[real_mask, "investment_score"] = (base + trend_boost).clip(0, 100)
        logger.info(
            "Recomputed investment_score (real BF + XL/XC trend boost) for %d tickers",
            real_mask.sum(),
        )
        # Reapply decision labels now that investment_score has changed
        master = apply_decision_labels(master, cfg)

    # ── Write output ──────────────────────────────────────────────────────
    csv_path = out_mod.write_csv(master, date_str, cfg.output_dir)
    json_path = out_mod.write_json(master, date_str, cfg.output_dir)

    master["date"] = date_str
    db = ScoresDB(cfg.output_dir / "scores.db")
    db.upsert_scores(master)
    db.log_signals(master, date_str)
    db.close()

    runtime = time.time() - t0
    logger.info("Scoring complete in %.1fs", runtime)

    # Build summary dict
    summary = {
        "date": date_str,
        "total_screened": len(tickers),
        "invest": master[master["action"] == "INVEST"]["ticker"].tolist(),
        "watch_exec": master[master["action"] == "WATCH_EXEC"]["ticker"].tolist(),
        "watch": master[master["action"] == "WATCH"]["ticker"].tolist(),
        "runtime_seconds": round(runtime, 2),
    }

    return ScoringResult(
        ranked_df=master.sort_values(
            "investment_score", ascending=False
        ).reset_index(drop=True),
        summary_dict=summary,
        scoring_date=date_str,
        total_screened=len(tickers),
        runtime_seconds=runtime,
        skipped=skipped_min_days,
    )


def get_ticker_history(ticker: str, cfg: Config, days: int = 60) -> pd.DataFrame:
    db = ScoresDB(cfg.output_dir / "scores.db")
    result = db.get_score_history(ticker, days)
    db.close()
    return result


def list_available_dates(cfg: Config) -> list[str]:
    db_path = cfg.output_dir / "scores.db"
    if not db_path.exists():
        return []
    db = ScoresDB(db_path)
    dates = db.get_available_dates()
    db.close()
    return dates


def get_summary(date: str, cfg: Config) -> dict:
    db = ScoresDB(cfg.output_dir / "scores.db")
    df = pd.read_sql_query(
        "SELECT * FROM scores_daily WHERE date = ? ORDER BY investment_score DESC",
        db._con,
        params=(date,),
    )
    db.close()
    if df.empty:
        return {}
    summary = {
        "date": date,
        "total_screened": len(df),
        "invest": df[df["action"] == "INVEST"]["ticker"].tolist(),
        "watch_exec": df[df["action"] == "WATCH_EXEC"]["ticker"].tolist(),
        "watch": df[df["action"] == "WATCH"]["ticker"].tolist(),
    }
    return summary
