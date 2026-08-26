"""Observation-Only Microstructure Snapshot Recorder.

Captures real-time microstructure feature states during live bar evaluations without
interfering with or altering the active Champion strategy's trade decisions.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import polars as pl

from quant_platform.config.settings import settings
from quant_platform.observability.logger import logger


class ObservationSnapshot(BaseModel):
    """Counterfactual feature state at the time of a strategy evaluation."""
    timestamp_ms: int
    datetime_utc: str
    symbol: str = "ETHUSDT"
    strategy_id: str
    action: str # LONG, SHORT, NO_TRADE
    current_price: float
    # Microstructure Observation Primitives
    delta_1m: float = 0.0
    rel_delta_1m: float = 0.0
    cvd_bearish_divergence: bool = False
    cvd_bullish_divergence: bool = False
    trade_imbalance_1m: float = 0.0
    open_interest: float = 0.0
    oi_change_pct_15m: float = 0.0
    joint_price_oi_regime: str = "NEUTRAL"
    is_liquidation_burst: bool = False
    # SMC & Structural Context
    market_regime: str = "UNKNOWN"
    structural_trend: str = "NEUTRAL"


class ObservationEngine:
    """Records passive microstructure snapshots for counterfactual research."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or (settings.research_dir / "audit" / "observation")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def record_snapshot(
        self,
        timestamp_ms: int,
        symbol: str,
        strategy_id: str,
        action: str,
        current_price: float,
        df_15m_with_microstructure: pl.DataFrame,
    ) -> ObservationSnapshot:
        """Extract latest feature row and persist counterfactual observation record."""
        dt_str = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        date_str = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

        last_row = df_15m_with_microstructure.tail(1).to_dicts()[0] if not df_15m_with_microstructure.is_empty() else {}

        snapshot = ObservationSnapshot(
            timestamp_ms=timestamp_ms,
            datetime_utc=dt_str,
            symbol=symbol,
            strategy_id=strategy_id,
            action=action,
            current_price=current_price,
            delta_1m=float(last_row.get("delta_1m", 0.0) or 0.0),
            rel_delta_1m=float(last_row.get("rel_delta_1m", 0.0) or 0.0),
            cvd_bearish_divergence=bool(last_row.get("is_cvd_bearish_divergence", False)),
            cvd_bullish_divergence=bool(last_row.get("is_cvd_bullish_divergence", False)),
            trade_imbalance_1m=float(last_row.get("trade_imbalance_1m", 0.0) or 0.0),
            open_interest=float(last_row.get("open_interest", 0.0) or 0.0),
            oi_change_pct_15m=float(last_row.get("oi_change_pct_15m", 0.0) or 0.0),
            joint_price_oi_regime=str(last_row.get("joint_price_oi_regime", "NEUTRAL")),
            is_liquidation_burst=bool(last_row.get("is_liquidation_burst", False)),
            market_regime=str(last_row.get("regime_type", "UNKNOWN")),
            structural_trend=str(last_row.get("market_structure_trend", "NEUTRAL")),
        )

        file_path = self.log_dir / f"observation_{date_str}.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot.model_dump()) + "\n")

        return snapshot
