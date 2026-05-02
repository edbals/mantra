#!/usr/bin/env python3
"""
Mantra 2.0 — IDX Stock Screener
================================
Two-stage scoring with real per-broker Index Alpha data on top 100 by FF×ADV blend.
- Stage 1: 5 components (broker_flow_proxy, float_pressure, structure, liquidity, catalyst)
- Stage 2: real broker flow (z-score sustained buyers, XL/XC trend, retail absorption)
- Investment score = weighted base + XL/XC trend boost (LOW float +5, MID +3, HIGH +1)
- Decision = INVEST | WATCH_EXEC | WATCH | OBSERVE | AVOID | ILLIQUID

Entry point: python main.py [--date YYYYMMDD] [--config config.json] [--incremental]
"""

VERSION = "2.2"

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("mantra")


def _print_results(df: pd.DataFrame, scoring_date: str, cfg, skipped: list,
                   total_screened: int | None = None, runtime: float | None = None) -> None:
    top = df[
        (df["action"] != "ILLIQUID")
        & (df.get("broker_data_source", pd.Series("proxy", index=df.index)) == "indexalpha")
    ].head(30)
    invest_tickers   = df[df["action"] == "INVEST"]["ticker"].tolist()
    watch_ex_tickers = df[df["action"] == "WATCH_EXEC"]["ticker"].tolist()
    n = total_screened if total_screened is not None else len(df)
    rt = f"  |  {runtime:.1f}s" if runtime is not None else ""

    print(f"\n{'='*100}")
    print(f"  MANTRA {VERSION}  |  Scoring date: {scoring_date}  |  {n} tickers screened{rt}")
    print(f"  Showing: {len(top)} Stage-2 tickers (real broker flow)  |  INVEST: {len(invest_tickers)}  |  WATCH_EXEC: {len(watch_ex_tickers)}")
    print(f"{'='*100}")
    print(f"  {'#':<4} {'Ticker':<8} {'Action':<10} {'Inv':>5} {'Brkout':>6}  {'BrkFlow*':>9} {'FloatPrs':>9} {'Struct':>7} {'Liq':>5} {'Cat':>5}  {'Top Buyers'}")
    print(f"  {'-'*96}")
    for i, (_, row) in enumerate(top.iterrows(), 1):
        brkout  = "YES" if row.get("breakout_signal") else "no"
        bf_val  = row.get("broker_flow_real_score", 0) or 0
        buyers  = str(row.get("top_buyers", ""))[:35]
        action  = row.get("action", "")
        print(
            f"  {i:<4} {row['ticker']:<8} {action:<10} "
            f"{row['investment_score']:>5.1f} "
            f"{brkout:>6}  "
            f"{bf_val:>9.1f} "
            f"{row.get('float_pressure_score', 0):>9.1f} "
            f"{row.get('structure_score', 0):>7.1f} "
            f"{row.get('liquidity_score', 0):>5.1f} "
            f"{row.get('catalyst_score', 0):>5.1f}  "
            f"{buyers}"
        )
    print(f"{'='*100}")
    print(f"  All scores = real broker flow (Index Alpha Stage 2)")
    print(f"  Output: {cfg.output_dir}/scores_{scoring_date}.csv")

    # ── XL/XC trend selling alert table — blended with free float ────────────
    if "xl_xc_trend_selling" in df.columns:
        _ff_rank = {"LOW": 3, "MID": 2, "HIGH": 1}
        trend = df[df["xl_xc_trend_selling"] == True].copy()
        if not trend.empty:
            trend["_ff_rank"] = trend.get("ff_category", pd.Series("", index=trend.index)).map(_ff_rank).fillna(0)
            trend = trend.sort_values(["_ff_rank", "xl_xc_trend_days"], ascending=[False, False])
            print(f"\n  !! RETAIL EXIT TREND  —  XL/XC net selling 3+ of last 10 days  (LOW float first)")
            print(f"  {'Ticker':<8} {'FF':>4}  {'Days':>5}  {'Top Sellers':<40}  {'Inv':>5}  {'Action'}")
            print(f"  {'-'*85}")
            for _, row in trend.iterrows():
                ff_cat = str(row.get("ff_category", ""))
                print(
                    f"  {row['ticker']:<8} {ff_cat:>4}  {int(row['xl_xc_trend_days']):>5}d  "
                    f"{str(row.get('top_sellers',''))[:40]:<40}  "
                    f"{row['investment_score']:>5.1f}  {row.get('action','')}"
                )
    # ── Suspended tickers warning ────────────────────────────────────────────
    if "suspension_flag" in df.columns:
        suspended = df[df["suspension_flag"] == 1]["ticker"].tolist()
        if suspended:
            print(f"  !! SUSPENDED: {', '.join(suspended)} — forced AVOID")

    print()

    if skipped:
        logger.info(
            "Skipped %d tickers due to insufficient history (<%d trading days)",
            len(skipped), cfg.min_trading_days,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MyMantra stock screener"
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Scoring date in YYYYMMDD format. Defaults to most recent trading day in DB.",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json (default: ./config.json)",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip scoring if output CSV for this date already exists (safe for cron).",
    )
    args = parser.parse_args()

    # Load config (validates weight sums at startup)
    from src.config import Config
    try:
        cfg = Config.load(args.config)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Config error: %s", e)
        sys.exit(1)

    # Incremental guard — resolve date early and skip if CSV already exists
    if args.incremental:
        from src.loader import IDXLoader
        _loader = IDXLoader(cfg)
        _scoring_ts = _loader.resolve_scoring_date(cfg.scoring_date if args.date is None else args.date)
        _loader.close()
        _date_str = str(_scoring_ts.date())
        _csv_path = Path(cfg.output_dir) / f"scores_{_date_str}.csv"
        if _csv_path.exists():
            logger.info("Incremental: %s already scored — loading existing results.", _date_str)
            df = pd.read_csv(_csv_path)
            df["investment_score"] = pd.to_numeric(df["investment_score"], errors="coerce").fillna(0)
            df = df.sort_values("investment_score", ascending=False).reset_index(drop=True)
            _print_results(df, _date_str, cfg, skipped=[], total_screened=len(df))
            return

    # Run scoring engine
    from src.engine import score_date
    try:
        result = score_date(args.date, cfg)
    except RuntimeError as e:
        logger.error("%s", e)
        sys.exit(1)

    _print_results(
        result.ranked_df,
        result.scoring_date,
        cfg,
        skipped=result.skipped,
        total_screened=result.total_screened,
        runtime=result.runtime_seconds,
    )


if __name__ == "__main__":
    main()
