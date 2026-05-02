"""
Quick test: run real broker flow scoring for 50 random tickers.
Usage:
    cd /Users/edbert/mantra
    python3 scripts/test_real_broker_flow.py
"""
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.loader import IDXLoader
from src.indexalpha import IndexAlphaClient
from src.features.broker_flow_real import compute_real

CFG_PATH = Path(__file__).parent.parent / "config.json"

cfg          = Config.load(CFG_PATH)
loader       = IDXLoader(cfg)
broker_master = loader.load_broker_master(cfg.broker_master_csv)
loader.close()

# Load latest scores CSV for ticker list
csvs = sorted(cfg.output_dir.glob("scores_*.csv"), reverse=True)
if not csvs:
    print("No scores CSV found. Run: python3 main.py first.")
    sys.exit(1)

scores_df    = pd.read_csv(csvs[0])
scoring_date = csvs[0].stem.replace("scores_", "")
from_date    = str((pd.Timestamp(scoring_date) - pd.Timedelta(days=30)).date())

# Pick 50 random tickers that have free float data
pool = scores_df[scores_df["free_float_pct"].notna()]["ticker"].tolist()
random.seed(42)
tickers = random.sample(pool, min(50, len(pool)))

print(f"\nScoring date : {scoring_date}")
print(f"Period from  : {from_date}")
print(f"Tickers      : {len(tickers)}")
print(f"Broker master: {len(broker_master)} brokers loaded")

# Get 20 trading dates from IDX-API
from src.loader import IDXLoader
loader2 = IDXLoader(cfg)
snap = loader2.load_stock_summary(pd.Timestamp(scoring_date), 20)
loader2.close()
trading_dates = sorted(
    snap[snap["date"] <= pd.Timestamp(scoring_date)]["date"]
    .drop_duplicates()
    .apply(lambda d: str(d.date()) if hasattr(d, "date") else str(d))
    .tolist()
)[-20:]
print(f"Trading dates: {trading_dates[0]} → {trading_dates[-1]} ({len(trading_dates)} days)")

print("\nPrefetching 20-day history for z-scores...")
client = IndexAlphaClient(
    api_key=cfg.indexalpha_api_key,
    db_path=cfg.output_dir / "scores.db",
)
fetched, skipped = client.prefetch_history(tickers, trading_dates)
print(f"  Fetched: {fetched}  Cached hits: {skipped}")
print("\nComputing real broker flow scores...")

real_df = compute_real(
    tickers=tickers,
    scoring_date=scoring_date,
    from_date=from_date,
    client=client,
    broker_master_df=broker_master,
)

# Rename to match Option B column name
if "broker_flow_score" in real_df.columns:
    real_df = real_df.rename(columns={"broker_flow_score": "broker_flow_real_score"})

# Merge proxy scores alongside
proxy = scores_df[scores_df["ticker"].isin(tickers)].set_index("ticker")
real_df["proxy_broker_flow"] = proxy["broker_flow_score"].reindex(real_df.index)
real_df["proxy_investment"]  = proxy["investment_score"].reindex(real_df.index)

# Sort by real score desc
out = real_df[real_df["broker_data_source"] == "indexalpha"].copy()
out = out.sort_values("broker_flow_real_score", ascending=False)

failed = real_df[real_df["broker_data_source"] == "proxy"]

print(f"{'='*110}")
print(f"  REAL BROKER FLOW TEST  |  {scoring_date}  |  {len(out)} succeeded  |  {len(failed)} fell back to proxy")
print(f"{'='*110}")

hdr = (
    f"  {'Ticker':<7} {'RealBF':>6} {'ProxyBF':>7} {'Delta':>6}  "
    f"{'AbsRatio':>8} {'RetSell':>7} {'Streak':>6} {'Adj':>5}  "
    f"{'Top Buyers':<35} {'Top Sellers'}"
)
print(hdr)
print(f"  {'-'*106}")

for ticker, row in out.iterrows():
    real_bf  = row.get("broker_flow_real_score", 0)
    proxy_bf = row.get("proxy_broker_flow", 0)
    delta    = real_bf - proxy_bf if pd.notna(proxy_bf) else 0
    delta_s  = f"{delta:+.1f}"
    absr     = row.get("absorption_ratio", 0)
    retsell  = row.get("retail_sell_share", 0)
    streak   = int(row.get("accum_streak", 0))
    adj      = row.get("score_adj", 0)
    buyers   = str(row.get("top_buyers", ""))[:35]
    sellers  = str(row.get("top_sellers", ""))[:30]

    print(
        f"  {ticker:<7} {real_bf:>6.1f} {proxy_bf:>7.1f} {delta_s:>6}  "
        f"{absr:>8.2f} {retsell:>7.3f} {streak:>6}  {adj:>5.1f}  "
        f"{buyers:<35} {sellers}"
    )

if not failed.empty:
    print(f"\n  Fell back to proxy: {', '.join(failed.index.tolist())}")

# Summary stats
print(f"\n  {'─'*60}")
print("  SUMMARY")
print(f"  {'─'*60}")
print(f"  Real BF score   — mean: {out['broker_flow_real_score'].mean():.1f}  max: {out['broker_flow_real_score'].max():.1f}  min: {out['broker_flow_real_score'].min():.1f}")
if "proxy_broker_flow" in out.columns:
    deltas = out["broker_flow_real_score"] - out["proxy_broker_flow"].fillna(0)
    print(f"  Delta vs proxy  — mean: {deltas.mean():+.1f}  max: {deltas.max():+.1f}  min: {deltas.min():+.1f}")
print(f"  With presence boost (adj>0): {(out['score_adj'] > 0).sum()} tickers")
print(f"  XL/XC selling flag:          {out['xl_xc_selling'].sum()} tickers")
sustained = out[out["sustained_buyers"].str.len() > 0]
print(f"  Sustained buyers found:      {len(sustained)} tickers")
if len(sustained):
    for t, row in sustained.iterrows():
        print(f"    {t}: {row['sustained_buyers']}")
print()
