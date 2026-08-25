"""Causal Decision and NO_TRADE Audit Logger.

Persistently logs every single bar evaluation, explicitly capturing the exact
rationale when NO_TRADE is decided (e.g. R:R < 1.5, Regime Mismatch, No structural trigger).
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from quant_platform.config.settings import settings
from quant_platform.observability.logger import logger


class DecisionRecord(BaseModel):
    """Structured decision audit log per candle evaluation."""
    timestamp_ms: int
    datetime_utc: str
    symbol: str
    strategy_id: str
    action: str # LONG, SHORT, NO_TRADE
    decision_reason: str
    market_regime: str
    current_price: float
    structural_trend: int
    active_fvgs: int
    details: Dict[str, Any] = Field(default_factory=dict)


class DecisionLogger:
    """Writes immutable jsonl audit records for every live decision evaluation."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or (settings.research_dir / "audit" / "decisions")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_decision(
        self,
        timestamp_ms: int,
        symbol: str,
        strategy_id: str,
        action: str,
        reason: str,
        market_regime: str,
        current_price: float,
        structural_trend: int = 0,
        active_fvgs: int = 0,
        details: Optional[Dict[str, Any]] = None,
    ) -> DecisionRecord:
        """Write structured audit decision to daily jsonl file."""
        dt_str = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        date_file_str = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

        record = DecisionRecord(
            timestamp_ms=timestamp_ms,
            datetime_utc=dt_str,
            symbol=symbol,
            strategy_id=strategy_id,
            action=action,
            decision_reason=reason,
            market_regime=market_regime,
            current_price=current_price,
            structural_trend=structural_trend,
            active_fvgs=active_fvgs,
            details=details or {},
        )

        file_path = self.log_dir / f"decisions_{date_file_str}.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump()) + "\n")

        return record
