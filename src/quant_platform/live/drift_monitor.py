"""Statistical Drift and Feature Frequency Monitor.

Monitors live setup frequency, trade rate, and feature distributions against
historical baseline expectations to detect regime shifts, data issues, or execution anomalies.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from quant_platform.observability.logger import logger


class DriftStatus(BaseModel):
    """Statistical health and drift report."""
    strategy_id: str
    historical_trade_frequency_per_100_bars: float
    live_trade_frequency_per_100_bars: float
    bars_monitored: int
    live_signals_detected: int
    drift_ratio: float
    has_drift_alert: bool
    drift_alert_message: Optional[str] = None


class DriftMonitor:
    """Detects behavioral drift between backtest expectations and live shadow stream."""

    def __init__(
        self,
        strategy_id: str,
        expected_trade_frequency_per_100_bars: float = 1.5,
    ):
        self.strategy_id = strategy_id
        self.expected_freq = max(0.01, expected_trade_frequency_per_100_bars)
        self.total_bars_monitored: int = 0
        self.live_signals_count: int = 0

    def record_bar_evaluation(self, is_signal_triggered: bool) -> None:
        """Update monitor counters on every evaluated bar."""
        self.total_bars_monitored += 1
        if is_signal_triggered:
            self.live_signals_count += 1

    def check_drift(self) -> DriftStatus:
        """Evaluate if live signal generation has statistically drifted from expectation."""
        if self.total_bars_monitored < 50:
            return DriftStatus(
                strategy_id=self.strategy_id,
                historical_trade_frequency_per_100_bars=self.expected_freq,
                live_trade_frequency_per_100_bars=0.0,
                bars_monitored=self.total_bars_monitored,
                live_signals_detected=self.live_signals_count,
                drift_ratio=1.0,
                has_drift_alert=False,
                drift_alert_message="Insufficient live sample size (<50 bars)",
            )

        live_freq = (self.live_signals_count / self.total_bars_monitored) * 100.0
        drift_ratio = live_freq / self.expected_freq

        has_alert = False
        msg = None

        if drift_ratio < 0.25:
            has_alert = True
            msg = f"STARVATION DRIFT: Live signal frequency ({live_freq:.2f}/100 bars) is <25% of expected ({self.expected_freq:.2f})."
        elif drift_ratio > 3.5:
            has_alert = True
            msg = f"OVERTRADING DRIFT: Live signal frequency ({live_freq:.2f}/100 bars) is >350% of expected ({self.expected_freq:.2f})."

        return DriftStatus(
            strategy_id=self.strategy_id,
            historical_trade_frequency_per_100_bars=self.expected_freq,
            live_trade_frequency_per_100_bars=live_freq,
            bars_monitored=self.total_bars_monitored,
            live_signals_detected=self.live_signals_count,
            drift_ratio=drift_ratio,
            has_drift_alert=has_alert,
            drift_alert_message=msg,
        )
