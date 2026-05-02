"""Index Alpha API client with local SQLite caching."""
from __future__ import annotations

import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    def _call_api(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        investor: str,
        timeout: tuple = (8, 20),
        _retries: int = 3,
    ) -> list[dict]:
        if not self._api_key or self._api_key.startswith("YOUR_"):
            raise ValueError("Index Alpha API key not configured in config.json")
        for attempt in range(_retries):
            resp = requests.get(
                f"{BASE_URL}/stocks/broker-summary",
                params={"ticker": ticker, "from": from_date, "to": to_date, "investor": investor},
                headers={"Authorization": f"Bearer {self._api_key}", "accept": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 429:
                wait = 2 ** attempt * 5   # 5s, 10s, 20s
                logger.warning("Rate limited — waiting %ds before retry (attempt %d/%d)", wait, attempt + 1, _retries)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                raise RuntimeError(f"API error: {payload.get('error')}")
            return payload.get("data") or []
        raise RuntimeError(f"Rate limit not resolved after {_retries} retries for {ticker} {from_date}")

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

    def _prefetch_one(
        self,
        ticker: str,
        date: str,
        investor: str,
        max_consec_failures: int = 3,
    ) -> str:
        """Fetch a single (ticker, date). Returns 'cached', 'fetched', or 'error'."""
        if self._is_cached(ticker, date, investor):
            return "cached"
        try:
            records = self._call_api(ticker, date, date, investor, timeout=(6, 15))
            if records:
                self._store(ticker, date, investor, records)
            return "fetched"
        except Exception as exc:
            logger.warning("prefetch failed %s %s: %s", ticker, date, exc)
            return "error"

    def prefetch_history(
        self,
        tickers: list[str],
        trading_dates: list[str],
        investor: str = "all",
        workers: int = 3,
        max_consec_errors: int = 4,
    ) -> tuple[int, int]:
        """
        Pre-fetch individual-day broker data for tickers × dates in parallel.
        Skips any (ticker, date) already in cache.
        Skips a ticker after max_consec_errors consecutive failures (API unreachable).
        Returns (fetched, skipped) counts.
        """
        fetched = skipped = errors = 0
        n_tickers = len(tickers)

        for t_idx, ticker in enumerate(tickers):
            # Build work list — skip already-cached dates up front
            needed = [d for d in trading_dates if not self._is_cached(ticker, d, investor)]
            already = len(trading_dates) - len(needed)
            skipped += already

            if not needed:
                print(f"  [{t_idx+1:>3}/{n_tickers}] {ticker:<8} all cached", flush=True)
                continue

            # Parallel fetch for this ticker's missing dates
            ticker_fetched = ticker_errors = consec_errors = 0
            futures = {}
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for date in needed:
                    fut = pool.submit(self._prefetch_one, ticker, date, investor)
                    futures[fut] = date

                for fut in as_completed(futures):
                    result = fut.result()
                    if result == "fetched":
                        ticker_fetched += 1
                        consec_errors = 0
                    elif result == "cached":
                        skipped += 1
                        consec_errors = 0
                    else:
                        ticker_errors += 1
                        errors += 1
                        consec_errors += 1

                    if consec_errors >= max_consec_errors:
                        logger.warning(
                            "%s: %d consecutive errors — skipping remaining dates",
                            ticker, consec_errors,
                        )
                        pool.shutdown(wait=False, cancel_futures=True)
                        break

            fetched += ticker_fetched
            status = f"fetched={ticker_fetched}" if ticker_fetched else "cached"
            if ticker_errors:
                status += f"  errors={ticker_errors}"
            print(f"  [{t_idx+1:>3}/{n_tickers}] {ticker:<8} {status}", flush=True)

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
