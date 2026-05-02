from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import Config

logger = logging.getLogger(__name__)

# ── Real column names in the IDX-API database ────────────────────────────────
# Dates are stored as Unix milliseconds (integer) in most tables.
# Ticker columns are named 'code', not 'ticker'.
# broker_summary has NO per-ticker column — it is broker-level aggregate only.

_MS_PER_DAY = 86_400_000


def _ms_to_date(ms_series: pd.Series) -> pd.Series:
    """Convert Unix-millisecond integers to pandas Timestamps (date only)."""
    return pd.to_datetime(ms_series, unit="ms", utc=True).dt.tz_convert(None).dt.normalize()


def _date_to_ms(dt: pd.Timestamp | datetime) -> int:
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


class IDXLoader:
    """Read-only access to the IDX-API SQLite database."""

    def __init__(self, cfg: Config) -> None:
        if not cfg.idxdb_path.exists():
            raise RuntimeError(
                f"IDX-API database not found at {cfg.idxdb_path}.\n"
                "Run the sync script first:\n"
                "  cd /Users/edbert/IDX-API\n"
                "  deno run -A sync_for_mantra.ts"
            )
        self._con = sqlite3.connect(str(cfg.idxdb_path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._cfg = cfg
        self._validate_tables()

    def _validate_tables(self) -> None:
        required = [
            "stock_summary",
            "company_profile",
            "daily_index",
            "sectoral_movement",
            "company_dividend",
            "right_offering",
            "stock_split",
            "company_announcement",
            "company_suspend",
        ]
        cur = self._con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        present = {row[0] for row in cur.fetchall()}
        missing = [t for t in required if t not in present]
        if missing:
            raise RuntimeError(
                f"Required tables missing from IDX-API database: {missing}\n"
                "Run: deno run -A sync_for_mantra.ts"
            )

    def resolve_scoring_date(self, scoring_date: str) -> pd.Timestamp:
        """Return the most recent trading date in the database when 'auto'."""
        if scoring_date != "auto":
            return pd.Timestamp(scoring_date)
        row = self._con.execute(
            "SELECT MAX(date) FROM stock_summary"
        ).fetchone()
        if row[0] is None:
            raise RuntimeError(
                "stock_summary table is empty. Run the sync script to download data."
            )
        ts = _ms_to_date(pd.Series([row[0]]))[0]
        logger.info("Resolved scoring_date=auto → %s", ts.date())
        return ts

    def load_stock_summary(self, scoring_date: pd.Timestamp, lookback_days: int) -> pd.DataFrame:
        """
        Load OHLCV + foreign + listed_shares for all tickers.
        Returns lookback_days of history up to and including scoring_date.
        """
        end_ms = _date_to_ms(scoring_date + pd.Timedelta(days=1))
        # Fetch extra calendar days to ensure we get enough trading days
        start_ms = _date_to_ms(scoring_date - pd.Timedelta(days=lookback_days * 3))

        df = pd.read_sql_query(
            """
            SELECT
                code        AS ticker,
                date        AS date_ms,
                open, high, low, close, volume, value, frequency,
                bid, bid_volume, offer, offer_volume,
                foreign_buy, foreign_sell, foreign_net,
                listed_shares
            FROM stock_summary
            WHERE date >= ? AND date < ?
              AND close IS NOT NULL
              AND volume > 0
            ORDER BY code, date
            """,
            self._con,
            params=(start_ms, end_ms),
        )
        if df.empty:
            raise RuntimeError(
                f"No stock data found around {scoring_date.date()}. "
                "Run the sync script to download data."
            )
        df["date"] = _ms_to_date(df["date_ms"])
        df = df.drop(columns=["date_ms"])
        logger.info(
            "Loaded stock_summary: %d rows, %d tickers, up to %s",
            len(df), df["ticker"].nunique(), scoring_date.date(),
        )
        return df

    def load_company_profiles(self) -> pd.DataFrame:
        """Load company name lookup (code → name)."""
        df = pd.read_sql_query(
            "SELECT code AS ticker, name AS company_name FROM company_profile",
            self._con,
        )
        return df

    def load_daily_index(self, scoring_date: pd.Timestamp, lookback_days: int) -> pd.DataFrame:
        """Load IHSG daily close prices."""
        end_ms = _date_to_ms(scoring_date + pd.Timedelta(days=1))
        start_ms = _date_to_ms(scoring_date - pd.Timedelta(days=lookback_days * 3))

        df = pd.read_sql_query(
            """
            SELECT date AS date_ms, name AS index_name, close
            FROM daily_index
            WHERE date >= ? AND date < ?
            ORDER BY date
            """,
            self._con,
            params=(start_ms, end_ms),
        )
        df["date"] = _ms_to_date(df["date_ms"])
        df = df.drop(columns=["date_ms"])
        return df

    def load_sectoral_movement(self, scoring_date: pd.Timestamp, lookback_days: int) -> pd.DataFrame:
        """Load sector daily change percentages."""
        end_ms = _date_to_ms(scoring_date + pd.Timedelta(days=1))
        start_ms = _date_to_ms(scoring_date - pd.Timedelta(days=lookback_days * 3))

        df = pd.read_sql_query(
            """
            SELECT date AS date_ms, name AS sector_name, change AS change_pct
            FROM sectoral_movement
            WHERE date >= ? AND date < ?
            ORDER BY date, name
            """,
            self._con,
            params=(start_ms, end_ms),
        )
        df["date"] = _ms_to_date(df["date_ms"])
        df = df.drop(columns=["date_ms"])
        return df

    def load_dividends(self, scoring_date: pd.Timestamp) -> pd.DataFrame:
        """Load upcoming cum-dividend dates."""
        # Look forward 60 days; look back 7 days for already-passed cum dates
        start_ms = _date_to_ms(scoring_date - pd.Timedelta(days=7))
        end_ms = _date_to_ms(scoring_date + pd.Timedelta(days=61))

        df = pd.read_sql_query(
            """
            SELECT code AS ticker, cum_dividend AS cum_date_ms, payment_date AS pay_date_ms
            FROM company_dividend
            WHERE cum_dividend IS NOT NULL
              AND cum_dividend >= ? AND cum_dividend <= ?
            """,
            self._con,
            params=(start_ms, end_ms),
        )
        if df.empty:
            return pd.DataFrame(columns=["ticker", "cum_date", "pay_date"])
        df["cum_date"] = _ms_to_date(df["cum_date_ms"])
        df["pay_date"] = _ms_to_date(df["pay_date_ms"])
        return df[["ticker", "cum_date", "pay_date"]]

    def load_right_offerings(self, scoring_date: pd.Timestamp) -> pd.DataFrame:
        """Load right offerings with exercise dates within 60 days."""
        start_ms = _date_to_ms(scoring_date)
        end_ms = _date_to_ms(scoring_date + pd.Timedelta(days=61))

        df = pd.read_sql_query(
            """
            SELECT code AS ticker, exercise_date AS date_ms
            FROM right_offering
            WHERE exercise_date IS NOT NULL
              AND exercise_date >= ? AND exercise_date <= ?
            """,
            self._con,
            params=(start_ms, end_ms),
        )
        if df.empty:
            return pd.DataFrame(columns=["ticker", "exercise_date"])
        df["exercise_date"] = _ms_to_date(df["date_ms"])
        return df[["ticker", "exercise_date"]]

    def load_stock_splits(self, scoring_date: pd.Timestamp) -> pd.DataFrame:
        """Load stock splits with listing dates within 30 days."""
        start_ms = _date_to_ms(scoring_date)
        end_ms = _date_to_ms(scoring_date + pd.Timedelta(days=31))

        df = pd.read_sql_query(
            """
            SELECT code AS ticker, listing_date AS date_ms
            FROM stock_split
            WHERE listing_date IS NOT NULL
              AND listing_date >= ? AND listing_date <= ?
            """,
            self._con,
            params=(start_ms, end_ms),
        )
        if df.empty:
            return pd.DataFrame(columns=["ticker", "split_date"])
        df["split_date"] = _ms_to_date(df["date_ms"])
        return df[["ticker", "split_date"]]

    def load_announcements(self, scoring_date: pd.Timestamp) -> pd.DataFrame:
        """Load company announcements in the past 7 days."""
        start_ms = _date_to_ms(scoring_date - pd.Timedelta(days=7))
        end_ms = _date_to_ms(scoring_date + pd.Timedelta(days=1))

        df = pd.read_sql_query(
            """
            SELECT company_code AS ticker, date AS date_ms, title
            FROM company_announcement
            WHERE date >= ? AND date < ?
            """,
            self._con,
            params=(start_ms, end_ms),
        )
        if df.empty:
            return pd.DataFrame(columns=["ticker", "date", "title"])
        df["date"] = _ms_to_date(df["date_ms"])
        return df[["ticker", "date", "title"]]

    def load_suspensions(self) -> pd.DataFrame:
        """Load recent suspension events. type = 'Suspend' or 'Unsuspend'."""
        df = pd.read_sql_query(
            """
            SELECT code AS ticker, date AS date_ms, type
            FROM company_suspend
            ORDER BY date DESC
            """,
            self._con,
        )
        if df.empty:
            return pd.DataFrame(columns=["ticker", "date", "type"])
        df["date"] = _ms_to_date(df["date_ms"])
        return df[["ticker", "date", "type"]]

    def load_freefloat_csv(self, path: Path) -> pd.DataFrame:
        """Load the free-float CSV. Reloaded on every run.

        Supports both old format (Free Float (%)) and new format (Free Float %, Category).
        Returns columns: ticker, free_float_pct (0.0–1.0), ff_category (LOW/MID/HIGH or None).
        """
        if not path.exists():
            logger.warning("Free-float CSV not found at %s — float pressure disabled", path)
            return pd.DataFrame(columns=["ticker", "free_float_pct", "ff_category"])
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()

        # Ticker column
        ticker_col = next((c for c in df.columns if c.lower() == "ticker"), None)
        if ticker_col is None:
            logger.error("No Ticker column in freefloat CSV")
            return pd.DataFrame(columns=["ticker", "free_float_pct", "ff_category"])
        df = df.rename(columns={ticker_col: "ticker"})
        df["ticker"] = df["ticker"].str.strip().str.upper()

        # Free float % column — handles both "Free Float %" and "Free Float (%)"
        pct_col = next(
            (c for c in df.columns if "free float" in c.lower() or "freefloat" in c.lower()),
            None,
        )
        if pct_col is None:
            logger.error("No free float percentage column found in %s", path)
            return pd.DataFrame(columns=["ticker", "free_float_pct", "ff_category"])
        df["free_float_pct"] = pd.to_numeric(df[pct_col], errors="coerce") / 100.0

        # Category column (LOW / MID / HIGH) — optional, present in new format
        cat_col = next((c for c in df.columns if "categor" in c.lower()), None)
        if cat_col:
            df["ff_category"] = df[cat_col].str.strip().str.upper()
        else:
            df["ff_category"] = None

        out = df[["ticker", "free_float_pct", "ff_category"]].dropna(subset=["ticker"])
        logger.info("Loaded %d free-float records from %s", len(out), path.name)
        return out

    def load_broker_master(self, path: Path) -> pd.DataFrame:
        """Load broker classification file.

        Supports broker_master_renamed.csv schema:
            Kode Perusahaan → broker_code  (primary key)
            Nama Perusahaan → broker_name
            class           → broker_class
            No              → dropped (sequential only, not a key)

        Class values: institutional, retail_mixed, retail_pure,
                      Market_Maker, Zombie, Emitent, unknown
        """
        empty = pd.DataFrame(columns=["broker_code", "broker_name", "broker_class"])

        # Prefer new file alongside configured path if it exists
        base = path.parent
        new_path = base / "broker_master_renamed.csv"
        resolved = new_path if new_path.exists() else path

        if not resolved.exists():
            logger.warning("broker_master not found at %s", resolved)
            return empty

        df = pd.read_csv(resolved)
        df.columns = df.columns.str.strip()

        df = df.rename(columns={
            "Kode Perusahaan": "broker_code",
            "Nama Perusahaan": "broker_name",
            "class":           "broker_class",
        })

        if "broker_code" not in df.columns:
            logger.error("No 'Kode Perusahaan' column in %s", resolved.name)
            return empty

        df["broker_code"]  = df["broker_code"].str.strip().str.upper()
        df["broker_name"]  = df["broker_name"].str.strip()
        df["broker_class"] = df["broker_class"].str.strip()

        out = df[["broker_code", "broker_name", "broker_class"]].dropna(subset=["broker_code"])
        logger.info("Loaded %d broker records from %s", len(out), resolved.name)
        return out

    def close(self) -> None:
        self._con.close()
