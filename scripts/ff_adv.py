"""
Free Float x ADV Screener  (standalone CLI)
============================================
Separate algorithm focused purely on supply-squeeze dynamics:
  LOW float + HIGH ADV = strongest setup

Free Float category:
  - Reads 'Category' column from freefloat CSV if present (LOW / MID / HIGH)
  - Falls back to computing from 'Free Float (%)' if column is missing:
      LOW = <=20%, MID = 20-40%, HIGH = >40%

ADV tier (20-day average daily value, IDR):
  LOW  < 1B  |  MID  1B-10B  |  HIGH  >10B

ADV Momentum: 5-day ADV / 20-day ADV  (>=1.5x = accelerating)

Blend score matrix (0-100):
  FF x ADV     LOW   MID   HIGH
  LOW           30    65    100
  MID           20    50     80
  HIGH          10    35     60

Usage:
    cd /Users/edbert/mantra
    python3 scripts/ff_adv.py
    python3 scripts/ff_adv.py --top 50
    python3 scripts/ff_adv.py --ff LOW          # only LOW float tickers
    python3 scripts/ff_adv.py --adv HIGH         # only HIGH ADV tickers
    python3 scripts/ff_adv.py --accel            # only accelerating momentum
    python3 scripts/ff_adv.py --blend 80         # min blend score
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import Config

CFG_PATH = Path(__file__).parent.parent / "config.json"

# ADV thresholds (IDR)
ADV_HIGH = 10_000_000_000   # 10B
ADV_MID  =  1_000_000_000   #  1B
ADV_MIN  =    500_000_000   # 500M (screener minimum)

# Free float thresholds — only used when CSV has no Category column
FF_LOW_MAX  = 20.0   # percent
FF_MID_MAX  = 40.0   # percent

# Momentum threshold
MOMENTUM_THRESH = 1.5

BLEND_MATRIX = {
    ("LOW",  "HIGH"): 100,
    ("LOW",  "MID"):   65,
    ("LOW",  "LOW"):   30,
    ("MID",  "HIGH"):  80,
    ("MID",  "MID"):   50,
    ("MID",  "LOW"):   20,
    ("HIGH", "HIGH"):  60,
    ("HIGH", "MID"):   35,
    ("HIGH", "LOW"):   10,
}


def fmt_idr(v) -> str:
    if pd.isna(v):
        return "N/A"
    v = float(v)
    if v >= 1e12:
        return f"{v/1e12:.1f}T"
    if v >= 1e9:
        return f"{v/1e9:.1f}B"
    if v >= 1e6:
        return f"{v/1e6:.0f}M"
    return f"{v:.0f}"


def classify_adv(adv: float) -> str:
    if adv >= ADV_HIGH:
        return "HIGH"
    if adv >= ADV_MID:
        return "MID"
    return "LOW"


def classify_ff_from_pct(pct: float) -> str:
    """Fallback: compute tier from percentage value."""
    if pct <= FF_LOW_MAX:
        return "LOW"
    if pct <= FF_MID_MAX:
        return "MID"
    return "HIGH"


def load_freefloat(path: Path) -> pd.DataFrame:
    """Load freefloat CSV.

    New format (indonesia_free_float.csv):
        Columns: Ticker, Company Name, Free Float %, Category
        Category values: LOW / MID / HIGH (pre-assigned)

    Old format (fallback):
        Columns: Ticker, Free Float (%)
        Category computed from percentage: LOW <15%, MID 15-30%, HIGH >=30%
    """
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    ticker_col = next((c for c in df.columns if c.lower() == "ticker"), None)
    if ticker_col is None:
        raise ValueError(f"No Ticker column in {path.name}. Found: {list(df.columns)}")

    pct_col = next(
        (c for c in df.columns if "free float" in c.lower() or "freefloat" in c.lower()),
        None,
    )
    cat_col = next((c for c in df.columns if "categor" in c.lower()), None)

    out = pd.DataFrame()
    out["ticker"] = df[ticker_col].str.strip().str.upper()

    if pct_col:
        out["ff_pct"] = pd.to_numeric(df[pct_col], errors="coerce")

    if cat_col:
        out["ff_cat"] = df[cat_col].str.strip().str.upper()
        print(f"  Free float category: using '{cat_col}' column (LOW/MID/HIGH from source)")
    elif pct_col:
        out["ff_cat"] = out["ff_pct"].apply(
            lambda x: classify_ff_from_pct(x) if pd.notna(x) else None
        )
        print(f"  Free float category: computed from '{pct_col}' (no Category column found)")
    else:
        raise ValueError(f"No free float or category column in {path.name}")

    return out.dropna(subset=["ff_cat"])


def load_adv_5d(idxdb_path: Path, scoring_date: str) -> dict[str, float]:
    """5-day average daily value from IDX-API for ADV momentum calculation."""
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
            SELECT code, value
            FROM stock_summary
            WHERE date >= ? AND date <= ?
              AND value > 0 AND close IS NOT NULL
            ORDER BY code, date DESC
            """,
            con,
            params=(cutoff_ms, end_ms),
        )
    finally:
        con.close()

    result = {}
    for code, grp in df.groupby("code"):
        recent = grp.head(5)
        if len(recent) >= 3:
            result[str(code)] = float(recent["value"].mean())
    return result


def run(args) -> None:
    cfg = Config.load(CFG_PATH)

    # ── Load scores CSV ───────────────────────────────────────────────────────
    if args.date:
        csv_path = cfg.output_dir / f"scores_{args.date}.csv"
    else:
        csvs = sorted(cfg.output_dir.glob("scores_*.csv"), reverse=True)
        if not csvs:
            print("ERROR: No scores CSV found. Run: python3 main.py")
            sys.exit(1)
        csv_path = csvs[0]

    print(f"\nScores file : {csv_path.name}")
    scores = pd.read_csv(csv_path)
    scoring_date = csv_path.stem.replace("scores_", "")

    # ── Load free float categories ────────────────────────────────────────────
    # Prefer the new file (with Category column) if it exists alongside the configured path
    base = cfg.freefloat_csv.parent
    new_ff = base / "indonesia_free_float.csv"
    ff_path = new_ff if new_ff.exists() else cfg.freefloat_csv
    print(f"Free float  : {ff_path.name}")
    ff_df = load_freefloat(ff_path)

    # ── Merge ─────────────────────────────────────────────────────────────────
    df = scores.merge(ff_df, on="ticker", how="inner")
    df = df[df["avg_daily_value_idr"] >= ADV_MIN].copy()

    # ── ADV tier ──────────────────────────────────────────────────────────────
    df["adv_cat"] = df["avg_daily_value_idr"].map(classify_adv)

    # ── Blend score ───────────────────────────────────────────────────────────
    df["blend"] = df.apply(
        lambda r: BLEND_MATRIX.get((r["ff_cat"], r["adv_cat"]), 0), axis=1
    )

    # ── ADV momentum (5d vs 20d) ──────────────────────────────────────────────
    print("Loading 5d ADV from IDX-API for momentum…")
    adv5 = load_adv_5d(cfg.idxdb_path, scoring_date)
    df["adv_5d"] = df["ticker"].map(adv5)
    df["momentum"] = (df["adv_5d"] / df["avg_daily_value_idr"]).round(2)
    df["accel"] = df["momentum"] >= MOMENTUM_THRESH

    # ── Filters ───────────────────────────────────────────────────────────────
    if args.ff:
        df = df[df["ff_cat"] == args.ff.upper()]
    if args.adv:
        df = df[df["adv_cat"] == args.adv.upper()]
    if args.accel:
        df = df[df["accel"]]
    if args.blend:
        df = df[df["blend"] >= args.blend]

    # Sort: blend DESC, momentum DESC, investment_score DESC
    df = df.sort_values(
        ["blend", "momentum", "investment_score"], ascending=False
    ).reset_index(drop=True)

    # ── Print table ───────────────────────────────────────────────────────────
    total = len(df)
    print(f"\n{'='*98}")
    print(f"  FREE FLOAT x ADV SCREENER  |  {scoring_date}  |  {total} tickers")
    print(f"{'='*98}")

    hdr = (
        f"  {'#':>3}  {'Ticker':<7} {'FF%':>6} {'FF':>5}  "
        f"{'ADV(20d)':>9} {'ADV':>5}  {'Blend':>5}  "
        f"{'ADV(5d)':>8} {'Mmtm':>6} {'~':>1}  "
        f"{'InvScr':>6}"
    )
    print(hdr)
    print(f"  {'-'*94}")

    for i, row in df.head(args.top).iterrows():
        ff_pct_s = f"{row['ff_pct']:.1f}%" if "ff_pct" in row and pd.notna(row.get("ff_pct")) else "  —  "
        adv20    = fmt_idr(row["avg_daily_value_idr"])
        adv5_s   = fmt_idr(row.get("adv_5d"))
        mom_s    = f"{row['momentum']:.2f}x" if pd.notna(row.get("momentum")) else " N/A"
        arrow    = "↑" if row["accel"] else " "
        inv_s    = f"{row.get('investment_score', 0):.1f}"

        print(
            f"  {i+1:>3}  {row['ticker']:<7} {ff_pct_s:>6} {row['ff_cat']:>5}  "
            f"{adv20:>9} {row['adv_cat']:>5}  {row['blend']:>5.0f}  "
            f"{adv5_s:>8} {mom_s:>6} {arrow:>1}  "
            f"{inv_s:>6}"
        )

    if total > args.top:
        print(f"  … {total - args.top} more tickers not shown (use --top {total} to see all)")

    # ── Breakdown ─────────────────────────────────────────────────────────────
    print(f"\n  {'─'*60}")
    print("  BLEND BREAKDOWN")
    print(f"  {'─'*60}")
    grp = df.groupby(["ff_cat", "adv_cat"]).size().reset_index(name="n")
    grp["blend"] = grp.apply(
        lambda r: BLEND_MATRIX.get((r["ff_cat"], r["adv_cat"]), 0), axis=1
    )
    grp = grp.sort_values("blend", ascending=False)
    for _, r in grp.iterrows():
        bar = "█" * min(int(r["n"] / 2), 40)
        print(f"  {r['ff_cat']:<5} FF x {r['adv_cat']:<5} ADV  "
              f"score={r['blend']:>3}  n={r['n']:>3}  {bar}")

    print(f"\n  Accelerating (>={MOMENTUM_THRESH}x momentum): {df['accel'].sum()}")
    print(f"  Blend = 100 : {(df['blend']==100).sum()} tickers")
    print(f"  Blend >= 80 : {(df['blend']>=80).sum()} tickers")
    print(f"  Blend >= 60 : {(df['blend']>=60).sum()} tickers")
    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Free Float x ADV Blend Screener")
    p.add_argument("--date",  help="Scores date YYYY-MM-DD (default: latest)")
    p.add_argument("--top",   type=int,   default=40,  help="Rows to display (default 40)")
    p.add_argument("--ff",    choices=["LOW","MID","HIGH"], help="Filter by FF category")
    p.add_argument("--adv",   choices=["LOW","MID","HIGH"], help="Filter by ADV category")
    p.add_argument("--blend", type=int,   help="Min blend score (e.g. 80)")
    p.add_argument("--accel", action="store_true", help="Only accelerating momentum tickers")
    run(p.parse_args())
