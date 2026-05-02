from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_DDL_SCORES_DAILY = """
CREATE TABLE IF NOT EXISTS scores_daily (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    date                    TEXT NOT NULL,
    ticker                  TEXT NOT NULL,
    broker_flow_score       REAL,
    float_pressure_score    REAL,
    structure_score         REAL,
    liquidity_score         REAL,
    catalyst_score          REAL,
    investment_score        REAL,
    breakout_signal         INTEGER,
    action                  TEXT,
    free_float_pct          REAL,
    effective_float_shares  REAL,
    avg_daily_value_idr     REAL,
    broker_data_source      TEXT,
    broker_flow_real_score  REAL,
    top_buyers              TEXT,
    top_sellers             TEXT,
    xl_xc_selling           INTEGER,
    sustained_buyers        TEXT,
    score_adj               REAL,
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, ticker)
);
"""

_DDL_SIGNAL_LOG = """
CREATE TABLE IF NOT EXISTS signal_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL,
    ticker            TEXT NOT NULL,
    action            TEXT NOT NULL,
    investment_score  REAL,
    breakout_signal   INTEGER,
    notes             TEXT
);
"""

# Columns that indicate the old schema — drop and recreate if present
_STALE_COLUMNS = {"exec_spread_score", "exec_breakout_score", "exec_regime_score", "execution_score"}


class ScoresDB:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(path), check_same_thread=False)
        self._migrate()
        self._con.execute(_DDL_SCORES_DAILY)
        self._con.execute(_DDL_SIGNAL_LOG)
        self._con.commit()
        logger.info("scores.db ready at %s", path)

    def _migrate(self) -> None:
        """Drop tables with old schema columns so they can be recreated."""
        for table in ("scores_daily", "signal_log"):
            cur = self._con.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cur.fetchone() is None:
                continue
            existing = {r[1] for r in self._con.execute(f"PRAGMA table_info({table})").fetchall()}
            if existing & _STALE_COLUMNS:
                logger.info("Migrating %s to new schema", table)
                self._con.execute(f"DROP TABLE {table}")
                self._con.commit()

    def upsert_scores(self, df: pd.DataFrame) -> None:
        """Insert or replace rows in scores_daily using only columns present in both df and table."""
        table_cols = {r[1] for r in self._con.execute("PRAGMA table_info(scores_daily)").fetchall()}
        df_cols = set(df.columns)
        cols = [c for c in [
            "date", "ticker",
            "broker_flow_score", "float_pressure_score", "structure_score",
            "liquidity_score", "catalyst_score", "investment_score",
            "breakout_signal", "action",
            "free_float_pct", "effective_float_shares", "avg_daily_value_idr",
            "broker_data_source", "broker_flow_real_score",
            "top_buyers", "top_sellers", "xl_xc_selling", "sustained_buyers", "score_adj",
        ] if c in table_cols and c in df_cols]

        rows = df[cols].to_dict(orient="records")
        placeholders = ", ".join([f":{c}" for c in cols])
        sql = f"INSERT OR REPLACE INTO scores_daily ({', '.join(cols)}) VALUES ({placeholders})"
        self._con.executemany(sql, rows)
        self._con.commit()
        logger.info("Upserted %d rows into scores_daily", len(rows))

    def log_signals(self, df: pd.DataFrame, date: str, notes: str = "") -> None:
        """Log INVEST/WATCH_EXEC signals to signal_log."""
        signal_actions = {"INVEST", "WATCH_EXEC"}
        keep = ["ticker", "action", "investment_score"]
        if "breakout_signal" in df.columns:
            keep.append("breakout_signal")
        signals = df[df["action"].isin(signal_actions)][keep].copy()
        signals["date"] = date
        signals["notes"] = notes
        if signals.empty:
            return
        cols = ["date", "ticker", "action", "investment_score", "notes"]
        if "breakout_signal" in signals.columns:
            cols.insert(4, "breakout_signal")
        placeholders = ", ".join([f":{c}" for c in cols])
        self._con.executemany(
            f"INSERT INTO signal_log ({', '.join(cols)}) VALUES ({placeholders})",
            signals[cols].to_dict(orient="records"),
        )
        self._con.commit()

    def get_score_history(self, ticker: str, days: int = 60) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM scores_daily WHERE ticker = ? ORDER BY date DESC LIMIT ?",
            self._con,
            params=(ticker, days),
        )

    def get_available_dates(self) -> list[str]:
        cur = self._con.execute(
            "SELECT DISTINCT date FROM scores_daily ORDER BY date DESC"
        )
        return [row[0] for row in cur.fetchall()]

    def close(self) -> None:
        self._con.close()
