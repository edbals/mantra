"""Index Alpha API client with local SQLite caching."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.indexalpha.id"

_DDL = """
CREATE TABLE IF NOT EXISTS broker_transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    NOT NULL,
    ticker        TEXT    NOT NULL,
    investor_type TEXT    NOT NULL DEFAULT 'all',
    broker_code   TEXT    NOT NULL,
    buy_freq      INTEGER,
    buy_volume    INTEGER,
    buy_value     REAL,
    sell_freq     INTEGER,
    sell_volume   INTEGER,
    sell_value    REAL,
    buy_avg       REAL,
    sell_avg      REAL,
    fetched_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, ticker, investor_type, broker_code)
);

CREATE TABLE IF NOT EXISTS broker_period_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_date     TEXT    NOT NULL,
    to_date       TEXT    NOT NULL,
    ticker        TEXT    NOT NULL,
    investor_type TEXT    NOT NULL DEFAULT 'all',
    broker_code   TEXT    NOT NULL,
    buy_volume    INTEGER,
    buy_value     REAL,
    sell_volume   INTEGER,
    sell_value    REAL,
    fetched_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_date, to_date, ticker, investor_type, broker_code)
);
"""


class IndexAlphaClient:
    def __init__(self, api_key: str, db_path: Path) -> None:
        self._api_key = api_key
        self._db_path = db_path
        self._ensure_table()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self._db_path), check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def _ensure_table(self) -> None:
        con = self._connect()
        con.executescript(_DDL)
        con.close()

    def _is_cached(self, ticker: str, date: str, investor: str) -> bool:
        con = self._connect()
        cur = con.execute(
            "SELECT 1 FROM broker_transactions WHERE ticker=? AND date=? AND investor_type=? LIMIT 1",
            (ticker, date, investor),
        )
        hit = cur.fetchone() is not None
        con.close()
        return hit

    def _call_api(self, ticker: str, from_date: str, to_date: str, investor: str) -> list[dict]:
        if not self._api_key or self._api_key.startswith("YOUR_"):
            raise ValueError("Index Alpha API key not configured in config.json")
        resp = requests.get(
            f"{BASE_URL}/stocks/broker-summary",
            params={"ticker": ticker, "from": from_date, "to": to_date, "investor": investor},
            headers={"Authorization": f"Bearer {self._api_key}", "accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            raise RuntimeError(f"API error: {payload.get('error')}")
        return payload.get("data") or []

    def _store(self, ticker: str, date: str, investor: str, records: list[dict]) -> None:
        con = self._connect()
        con.executemany(
            """
            INSERT OR REPLACE INTO broker_transactions
              (date, ticker, investor_type, broker_code,
               buy_freq, buy_volume, buy_value,
               sell_freq, sell_volume, sell_value,
               buy_avg, sell_avg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    date, ticker, investor, r["code"],
                    r.get("buy_freq"), r.get("buy_volume"), r.get("buy_value"),
                    r.get("sell_freq"), r.get("sell_volume"), r.get("sell_value"),
                    r.get("buy_avg"), r.get("sell_avg"),
                )
                for r in records
            ],
        )
        con.commit()
        con.close()
        logger.info("Cached %d brokers for %s %s (%s)", len(records), ticker, date, investor)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_broker_summary(
        self,
        ticker: str,
        date: str,
        investor: str = "all",
    ) -> pd.DataFrame:
        """
        Return broker summary DataFrame for ticker on date.
        Checks local cache first; calls API only on cache miss.
        Columns: code, buy_freq, buy_volume, buy_value,
                 sell_freq, sell_volume, sell_value, buy_avg, sell_avg, net_value
        """
        if not self._is_cached(ticker, date, investor):
            records = self._call_api(ticker, date, date, investor)
            if records:
                self._store(ticker, date, investor, records)
            # If records is empty (market closed / no data), still return empty DF below

        con = self._connect()
        df = pd.read_sql_query(
            """
            SELECT broker_code AS code,
                   buy_freq, buy_volume, buy_value,
                   sell_freq, sell_volume, sell_value,
                   buy_avg, sell_avg
            FROM broker_transactions
            WHERE ticker = ? AND date = ? AND investor_type = ?
            ORDER BY buy_value DESC
            """,
            con,
            params=(ticker, date, investor),
        )
        con.close()

        if not df.empty:
            df["net_value"]  = df["buy_value"].fillna(0) - df["sell_value"].fillna(0)
            df["net_volume"] = df["buy_volume"].fillna(0) - df["sell_volume"].fillna(0)

        return df

    def get_broker_history(
        self,
        ticker: str,
        dates: list[str],
        investor: str = "all",
    ) -> pd.DataFrame:
        """
        Fetch broker data for multiple dates.
        Each date is fetched and cached independently.
        Returns a long DataFrame with a 'date' column added.
        """
        frames = []
        for date in dates:
            if not self._is_cached(ticker, date, investor):
                try:
                    records = self._call_api(ticker, date, date, investor)
                    if records:
                        self._store(ticker, date, investor, records)
                except Exception as exc:
                    logger.warning("Skipping %s %s: %s", ticker, date, exc)
                    continue

            con = self._connect()
            df = pd.read_sql_query(
                """
                SELECT broker_code AS code, buy_volume, buy_value,
                       sell_volume, sell_value
                FROM broker_transactions
                WHERE ticker = ? AND date = ? AND investor_type = ?
                """,
                con,
                params=(ticker, date, investor),
            )
            con.close()
            if not df.empty:
                df["date"] = date
                df["net_volume"] = df["buy_volume"].fillna(0) - df["sell_volume"].fillna(0)
                df["net_value"]  = df["buy_value"].fillna(0)  - df["sell_value"].fillna(0)
                frames.append(df)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def get_period_summary(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        investor: str = "all",
    ) -> pd.DataFrame:
        """
        Return broker totals aggregated over a date range (one API call, no per-date detail).
        Cached in broker_period_cache keyed by (from_date, to_date, ticker, investor).

        Columns: code, buy_volume, buy_value, sell_volume, sell_value, net_volume, net_value
        """
        con = self._connect()
        cached = pd.read_sql_query(
            """
            SELECT broker_code AS code, buy_volume, buy_value, sell_volume, sell_value
            FROM broker_period_cache
            WHERE from_date=? AND to_date=? AND ticker=? AND investor_type=?
            """,
            con,
            params=(from_date, to_date, ticker, investor),
        )
        con.close()

        if cached.empty:
            try:
                records = self._call_api(ticker, from_date, to_date, investor)
            except Exception as exc:
                logger.warning("Period API failed for %s %s-%s: %s", ticker, from_date, to_date, exc)
                return pd.DataFrame()

            if records:
                con = self._connect()
                con.executemany(
                    """
                    INSERT OR REPLACE INTO broker_period_cache
                      (from_date, to_date, ticker, investor_type, broker_code,
                       buy_volume, buy_value, sell_volume, sell_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (from_date, to_date, ticker, investor, r["code"],
                         r.get("buy_volume"), r.get("buy_value"),
                         r.get("sell_volume"), r.get("sell_value"))
                        for r in records
                    ],
                )
                con.commit()
                con.close()
                logger.info("Cached period %s %s-%s (%d brokers)", ticker, from_date, to_date, len(records))

            # Re-query from cache
            con = self._connect()
            cached = pd.read_sql_query(
                """
                SELECT broker_code AS code, buy_volume, buy_value, sell_volume, sell_value
                FROM broker_period_cache
                WHERE from_date=? AND to_date=? AND ticker=? AND investor_type=?
                """,
                con,
                params=(from_date, to_date, ticker, investor),
            )
            con.close()

        if not cached.empty:
            cached["net_volume"] = cached["buy_volume"].fillna(0) - cached["sell_volume"].fillna(0)
            cached["net_value"]  = cached["buy_value"].fillna(0)  - cached["sell_value"].fillna(0)
        return cached

    def prefetch_history(
        self,
        tickers: list[str],
        trading_dates: list[str],
        investor: str = "all",
    ) -> tuple[int, int]:
        """
        Pre-fetch individual-day broker data for a list of tickers × dates.
        Skips any (ticker, date) already in cache.
        Returns (fetched, skipped) counts.

        Used to warm up the z-score history so sustained_buyers works from day 1.
        Cost: at most len(tickers) × len(trading_dates) API calls, minus cache hits.
        """
        fetched = skipped = errors = 0
        total = len(tickers) * len(trading_dates)
        done  = 0
        for t_idx, ticker in enumerate(tickers):
            ticker_new = 0
            for date in trading_dates:
                done += 1
                if self._is_cached(ticker, date, investor):
                    skipped += 1
                    continue
                try:
                    records = self._call_api(ticker, date, date, investor)
                    if records:
                        self._store(ticker, date, investor, records)
                    fetched += 1
                    ticker_new += 1
                except Exception as exc:
                    errors += 1
                    logger.warning("prefetch failed %s %s: %s", ticker, date, exc)

            pct = done / total * 100
            status = f"new={ticker_new}" if ticker_new else "cached"
            print(
                f"  [{pct:5.1f}%] {t_idx+1:>3}/{len(tickers)}  {ticker:<8} {status}",
                flush=True,
            )

        print(f"  Done — fetched={fetched}  cached={skipped}  errors={errors}", flush=True)
        logger.info("prefetch_history: fetched=%d skipped=%d errors=%d", fetched, skipped, errors)
        return fetched, skipped

    def check_usage(self) -> dict:
        """Return monthly usage stats from the API."""
        try:
            resp = requests.get(
                f"{BASE_URL}/usage",
                headers={"Authorization": f"Bearer {self._api_key}", "accept": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
        except Exception as exc:
            logger.error("Usage check failed: %s", exc)
            return {}
