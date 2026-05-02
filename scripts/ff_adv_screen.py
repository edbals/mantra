"""
Free Float x ADV Blend Screener
================================
Identifies stocks where low float + high average daily value (ADV) creates
a supply-squeeze signal. Also computes ADV momentum (5d vs 20d) to catch
stocks that are "waking up" — rising activity even if absolute ADV is still medium.

Usage:
    cd /Users/edbert/mantra
    python3 scripts/ff_adv_screen.py [--date YYYY-MM-DD] [--top N] [--min-adv B]

Classification:
    Free Float:  LOW <=20%  |  MEDIUM 20-40%  |  HIGH >40%
    ADV (20d):   LOW <1B    |  MEDIUM 1-10B   |  HIGH >10B  (IDR)

Blend score (0-100):
    FF x ADV    LOW   MEDIUM   HIGH
    LOW          30     65      100   <- supply squeeze + heavy demand
    MEDIUM       20     50       80
    HIGH         10     35       60
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import Config

CFG_PATH = Path(__file__).parent.parent / "config.json"

# ADV thresholds (IDR)
ADV_HIGH = 10_000_000_000   # 10 billion
ADV_LOW  =  1_000_000_000   #  1 billion
ADV_MIN  =    500_000_000   # 500 million (same as main screener minimum)

# Free float thresholds (ratio, not percent)
FF_LOW    = 0.20
FF_MEDIUM = 0.40

# ADV momentum: if 5d_adv / 20d_adv >= this → "accelerating"
MOMENTUM_THRESH = 1.5

BLEND_MATRIX = {
    ("LOW",    "HIGH"):   100,
    ("LOW",    "MEDIUM"):  65,
    ("LOW",    "LOW"):     30,
    ("MEDIUM", "HIGH"):    80,
    ("MEDIUM", "MEDIUM"):  50,
    ("MEDIUM", "LOW"):     20,
    ("HIGH",   "HIGH"):    60,
    ("HIGH",   "MEDIUM"):  35,
    ("HIGH",   "LOW"):     10,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def classify_ff(pct: float) -> str:
    if pct <= FF_LOW:
        return "LOW"
    if pct <= FF_MEDIUM:
        return "MEDIUM"
    return "HIGH"


def classify_adv(adv: float) -> str:
    if adv >= ADV_HIGH:
        return "HIGH"
    if adv >= ADV_LOW:
        return "MEDIUM"
    return "LOW"


def fmt_idr(v: float) -> str:
    if v >= 1e12:
        return f"{v/1e12:.1f}T"
    if v >= 1e9:
        return f"{v/1e9:.1f}B"
    if v >= 1e6:
        return f"{v/1e6:.0f}M"
    return f"{v:.0f}"


def load_adv_5d(idxdb_path: Path, tickers: list[str], scoring_date: str) -> dict[str, float]:
    """Query IDX-API for 5-day average daily value per ticker, ending on scoring_date."""
    if not idxdb_path.exists():
        return {}
    con = sqlite3.connect(str(idxdb_path), check_same_thread=False)
    cutoff_ms = int(
        (pd.Timestamp(scoring_date) - pd.Timedelta(days=14)).timestamp() * 1000
    )
    end_ms = int(
        (pd.Timestamp(scoring_date) + pd.Timedelta(days=1)).timestamp() * 1000
    )
    try:
        df = pd.read_sql_query(
            """
            SELECT code, date AS date_ms, value
            FROM stock_summary
            WHERE date >= ? AND date <= ?
              AND value > 0
              AND close IS NOT NULL
            ORDER BY code, date DESC
            """,
            con,
            params=(cutoff_ms, end_ms),
        )
    finally:
        con.close()

    if df.empty:
        return {}

    # Take 5 most recent trading days per ticker
    result = {}
    for code, grp in df.groupby("code"):
        recent = grp.head(5)
        if len(recent) >= 3:  # need at least 3 days
            result[code] = float(recent["value"].mean())
    return result


# ── Main ─────────────────────────────────────────────────────────────────────

def run(date: str | None, top_n: int, min_adv_b: float) -> None:
    cfg = Config.load(CFG_PATH)
    output_dir = cfg.output_dir

    # Find CSV
    if date:
        csv_path = output_dir / f"scores_{date}.csv"
    else:
        csvs = sorted(output_dir.glob("scores_*.csv"), reverse=True)
        if not csvs:
            print("No scores CSV found. Run: python3 main.py")
            sys.exit(1)
        csv_path = csvs[0]

    print(f"Loading: {csv_path.name}")
    df = pd.read_csv(csv_path)
    scoring_date = csv_path.stem.replace("scores_", "")

    # Filter: must have free float data + meet minimum ADV
    min_adv = min_adv_b * 1e9
    df = df[df["free_float_pct"].notna()].copy()
    df = df[df["avg_daily_value_idr"] >= min_adv].copy()

    print(f"Tickers with free float data + ADV ≥ {fmt_idr(min_adv)}: {len(df)}")

    # Classify
    df["ff_tier"]  = df["free_float_pct"].map(classify_ff)
    df["adv_tier"] = df["avg_daily_value_idr"].map(classify_adv)
    df["blend_score"] = df.apply(
        lambda r: BLEND_MATRIX.get((r["ff_tier"], r["adv_tier"]), 0), axis=1
    )

    # ADV momentum: load 5-day ADV from IDX-API
    print("Loading 5-day ADV from IDX-API…")
    adv5 = load_adv_5d(cfg.idxdb_path, df["ticker"].tolist(), scoring_date)
    df["adv_5d"] = df["ticker"].map(adv5)
    df["adv_momentum"] = (df["adv_5d"] / df["avg_daily_value_idr"]).round(2)
    df["accelerating"] = df["adv_momentum"] >= MOMENTUM_THRESH

    # Sort: blend_score DESC, then momentum DESC
    df = df.sort_values(
        ["blend_score", "adv_momentum"], ascending=False
    ).reset_index(drop=True)

    # ── Print table ───────────────────────────────────────────────────────────
    print(f"\n{'='*90}")
    print(f"  FREE FLOAT × ADV SCREENER  —  {scoring_date}  —  Top {top_n}")
    print(f"{'='*90}")
    header = (
        f"{'#':>3}  {'Ticker':<7} {'FF%':>6} {'FF':>6} "
        f"{'ADV (20d)':>10} {'ADV':>6} {'Blend':>5} "
        f"{'5d ADV':>9} {'Mmtm':>6} {'~':>2} {'InvScr':>7} {'Action'}"
    )
    print(header)
    print("-" * 95)

    for idx, (_, row) in enumerate(df.head(top_n).iterrows()):
        ff_pct = f"{row['free_float_pct']*100:.1f}%"
        adv20  = fmt_idr(row["avg_daily_value_idr"])
        adv5_s = fmt_idr(row["adv_5d"]) if pd.notna(row.get("adv_5d")) else "N/A"
        mom    = f"{row['adv_momentum']:.2f}x" if pd.notna(row.get("adv_momentum")) else "N/A"
        accel  = "↑" if row.get("accelerating") else " "
        inv    = f"{row.get('investment_score', 0):.1f}"
        print(
            f"{idx+1:>3}  {row['ticker']:<7} {ff_pct:>6} {row['ff_tier']:>6} "
            f"{adv20:>10} {row['adv_tier']:>6} {row['blend_score']:>5.0f} "
            f"{adv5_s:>9} {mom:>6} {accel:>2} {inv:>7}  {row.get('action','')}"
        )

    # ── Summary breakdown ─────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print("BLEND SCORE BREAKDOWN")
    print(f"{'─'*50}")
    grp = df.groupby(["ff_tier", "adv_tier"]).size().reset_index(name="count")
    grp["blend"] = grp.apply(
        lambda r: BLEND_MATRIX.get((r["ff_tier"], r["adv_tier"]), 0), axis=1
    )
    grp = grp.sort_values("blend", ascending=False)
    for _, r in grp.iterrows():
        bar = "█" * int(r["count"] / 2)
        print(f"  {r['ff_tier']:<7} FF × {r['adv_tier']:<7} ADV  score={r['blend']:>3}  n={r['count']:>3}  {bar}")

    print(f"\n  Accelerating (momentum ≥ {MOMENTUM_THRESH}x): {df['accelerating'].sum()} tickers")
    print(f"  Blend=100 (ideal):  {(df['blend_score']==100).sum()} tickers")
    print(f"  Blend≥80:           {(df['blend_score']>=80).sum()} tickers")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Free Float × ADV Blend Screener")
    parser.add_argument("--date", help="YYYY-MM-DD (default: latest CSV)")
    parser.add_argument("--top", type=int, default=40, help="Rows to display (default: 40)")
    parser.add_argument("--min-adv", type=float, default=0.5,
                        help="Minimum ADV in billions IDR (default: 0.5)")
    args = parser.parse_args()
    run(args.date, args.top, args.min_adv)
