from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

VALID_BROKER_CLASSES = {
    "institutional",   # large block trades for funds/banks/foreign entities
    "retail_mixed",    # serves both retail and institutional
    "retail_pure",     # app-based / online-first retail
    "Market_Maker",    # price-directional signal — they lead moves
    "Zombie",          # crossing/repo brokers — flow is not organic
    "Emitent",         # owner/controlling shareholder broker — insider flow
    "unknown",
}
VALID_CONFIDENCE = {"high", "medium", "low"}


@dataclass
class Weights:
    broker_flow: float
    float_pressure: float
    structure: float
    liquidity: float
    catalyst: float

    def validate(self) -> None:
        total = self.broker_flow + self.float_pressure + self.structure + self.liquidity + self.catalyst
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Investment weights must sum to 1.0 ±0.001, got {total:.6f}")


@dataclass
class ExecutionWeights:
    spread_proxy: float
    breakout_quality: float
    market_regime: float

    def validate(self) -> None:
        total = self.spread_proxy + self.breakout_quality + self.market_regime
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Execution weights must sum to 1.0 ±0.001, got {total:.6f}")


@dataclass
class Thresholds:
    invest: float
    watch: float
    observe: float


@dataclass
class Config:
    idxdb_path: Path
    freefloat_csv: Path
    broker_master_csv: Path
    output_dir: Path
    scoring_date: str  # "auto" or "YYYY-MM-DD"
    lookback_days: int
    lookback_weeks: int  # reserved; not used in current formulas (Q1)
    weights: Weights
    execution_weights: ExecutionWeights
    thresholds: Thresholds
    min_avg_daily_value_idr: float
    min_trading_days: int
    indexalpha_api_key: str = ""
    broker_watchlist: list = None  # type: ignore

    @classmethod
    def load(cls, path: str | Path = "config.json") -> "Config":
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"config.json not found at {config_path.resolve()}")

        with open(config_path) as f:
            raw = json.load(f)

        # Resolve paths relative to config file's directory
        base = config_path.parent

        def resolve(p: str) -> Path:
            return (base / p).resolve()

        weights = Weights(**raw["weights"])
        exec_weights = ExecutionWeights(**raw["execution_weights"])
        thresholds = Thresholds(**raw["thresholds"])

        # Validate weight sums at load time
        weights.validate()
        exec_weights.validate()

        cfg = cls(
            idxdb_path=resolve(raw["idxdb_path"]),
            freefloat_csv=resolve(raw["freefloat_csv"]),
            broker_master_csv=resolve(raw["broker_master_csv"]),
            output_dir=resolve(raw["output_dir"]),
            scoring_date=raw["scoring_date"],
            lookback_days=int(raw["lookback_days"]),
            lookback_weeks=int(raw["lookback_weeks"]),
            weights=weights,
            execution_weights=exec_weights,
            thresholds=thresholds,
            min_avg_daily_value_idr=float(raw["min_avg_daily_value_idr"]),
            min_trading_days=int(raw["min_trading_days"]),
            indexalpha_api_key=raw.get("indexalpha_api_key", ""),
            broker_watchlist=raw.get("broker_watchlist", []),
        )

        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Config loaded from %s", config_path.resolve())
        return cfg
