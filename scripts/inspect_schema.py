#!/usr/bin/env python3
"""
Run this script BEFORE building loader.py.
It connects to the IDX-API SQLite database and prints the actual column
names and types for every table the scoring engine reads.

Usage:
    cd /Users/edbert/mantra
    python scripts/inspect_schema.py
    python scripts/inspect_schema.py --config /path/to/config.json
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Tables the scoring engine depends on (Section 4.1)
REQUIRED_TABLES = [
    "stock_summary",
    "broker_summary",
    "company_profiles",
    "financial_ratios",
    "dividend_announcements",
    "right_offerings",
    "stock_splits",
    "announcements",
    "suspend_data",
    "daily_indices",
    "foreign_trading",
    "sectoral_movement",
]

# Logical → expected column names (from spec §4.2) — for diff comparison only
EXPECTED_COLUMNS = {
    "stock_summary": ["date", "ticker", "open", "high", "low", "close", "volume", "value", "frequency"],
    "broker_summary": ["date", "ticker", "broker_code", "buy_lot", "sell_lot", "buy_value", "sell_value", "buy_frequency", "sell_frequency"],
    "company_profiles": ["ticker", "company_name", "listed_shares"],
    "foreign_trading": ["date", "ticker", "foreign_net_buy"],
    "daily_indices": ["date", "close"],
    "dividend_announcements": ["ticker", "cum_date"],
    "right_offerings": ["ticker"],
    "stock_splits": ["ticker"],
    "announcements": ["ticker", "date"],
    "suspend_data": ["ticker", "date"],
    "sectoral_movement": ["date", "sector"],
}


def inspect(db_path: Path) -> None:
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        print("Make sure you have run the IDX-API sync functions first:")
        print("  deno task db:sync")
        print("  syncStockSummary(), syncBrokerSummary(), syncCompanyProfile(),")
        print("  syncDailyIndex(), syncForeignTrading(), syncCompanyDividend(), syncBrokerParticipant()")
        sys.exit(1)

    con = sqlite3.connect(str(db_path), check_same_thread=False)
    cur = con.cursor()

    # Get all tables actually in the DB
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    existing = {row[0] for row in cur.fetchall()}

    print(f"\n{'='*60}")
    print(f"IDX-API Database: {db_path}")
    print(f"{'='*60}")
    print(f"All tables present ({len(existing)}): {sorted(existing)}\n")

    missing_required = []
    for table in REQUIRED_TABLES:
        print(f"{'─'*50}")
        print(f"TABLE: {table}")
        if table not in existing:
            print(f"  *** MISSING — run the relevant sync function ***")
            missing_required.append(table)
            continue

        cur.execute(f"PRAGMA table_info({table})")
        cols = cur.fetchall()
        # cols: (cid, name, type, notnull, dflt_value, pk)
        col_names = [c[1] for c in cols]
        print(f"  Columns ({len(col_names)}):")
        for c in cols:
            pk_flag = " [PK]" if c[5] else ""
            nn_flag = " NOT NULL" if c[3] else ""
            print(f"    {c[0]:>2}  {c[1]:<35} {c[2]:<15}{nn_flag}{pk_flag}")

        # Row count
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
        print(f"  Row count: {row_count:,}")

        # Date range if a 'date'-like column exists
        date_col = next((c[1] for c in cols if "date" in c[1].lower()), None)
        if date_col:
            cur.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table}")
            mn, mx = cur.fetchone()
            print(f"  Date range ({date_col}): {mn} → {mx}")

        # Flag divergences from expected schema
        expected = EXPECTED_COLUMNS.get(table, [])
        if expected:
            missing_cols = [c for c in expected if c not in col_names]
            if missing_cols:
                print(f"  !! EXPECTED columns not found: {missing_cols}")
                print(f"     Actual columns: {col_names}")
            else:
                print(f"  Schema matches expected columns for this table.")

    con.close()

    print(f"\n{'='*60}")
    if missing_required:
        print(f"MISSING REQUIRED TABLES ({len(missing_required)}): {missing_required}")
        print("Run the IDX-API sync functions for each missing table before proceeding.")
    else:
        print("All required tables present. Paste this output back to build loader.py.")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect IDX-API SQLite schema")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--db", help="Direct path to idx.db (overrides config)")
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db).resolve()
    else:
        import json
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"ERROR: config.json not found at {config_path.resolve()}")
            print("Either fill in config.json or pass --db /path/to/idx.db directly.")
            sys.exit(1)
        with open(config_path) as f:
            cfg = json.load(f)
        # Resolve relative to config file location
        db_path = (config_path.parent / cfg["idxdb_path"]).resolve()

    inspect(db_path)


if __name__ == "__main__":
    main()
