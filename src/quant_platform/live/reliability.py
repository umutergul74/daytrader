"""Operational Reliability and Telemetry Monitoring Engine.

Tracks market-data uptime, WebSocket reconnects, REST gap recoveries, signal engine
decisions, paper-broker state transitions, and Telegram notification delivery metrics.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from quant_platform.config.settings import settings
from quant_platform.observability.logger import logger


class MarketDataTelemetry(BaseModel):
    """Market data stream health and latency telemetry."""
    websocket_connected: bool = False
    total_messages_received: int = 0
    reconnect_count: int = 0
    total_reconnect_duration_seconds: float = 0.0
    rest_recovery_events_count: int = 0
    duplicate_events_count: int = 0
    missing_candles_count: int = 0
    stale_data_events_count: int = 0
    last_data_latency_ms: int = 0
    max_data_latency_ms: int = 0


class SignalEngineTelemetry(BaseModel):
    """Signal generation and evaluation telemetry."""
    total_bar_evaluations: int = 0
    long_signals_generated: int = 0
    short_signals_generated: int = 0
    no_trade_decisions: int = 0
    duplicate_signals_blocked: int = 0
    expired_setups_count: int = 0
    risk_engine_rejections_count: int = 0


class PaperBrokerTelemetry(BaseModel):
    """Paper execution and order lifecycle telemetry."""
    simulated_entries_count: int = 0
    stop_loss_events_count: int = 0
    take_profit_events_count: int = 0
    total_fees_debited: float = 0.0
    total_slippage_incurred: float = 0.0
    unexpected_state_transitions: int = 0


class NotificationTelemetry(BaseModel):
    """Notification delivery telemetry."""
    telegram_dispatches_success: int = 0
    telegram_dispatches_failed: int = 0
    duplicate_notifications_blocked: int = 0
    average_dispatch_latency_ms: float = 0.0


class DailyReliabilityRecord(BaseModel):
    """Consolidated daily operational reliability record."""
    timestamp_ms: int
    datetime_utc: str
    symbol: str = "ETHUSDT"
    market_data: MarketDataTelemetry = Field(default_factory=MarketDataTelemetry)
    signal_engine: SignalEngineTelemetry = Field(default_factory=SignalEngineTelemetry)
    paper_broker: PaperBrokerTelemetry = Field(default_factory=PaperBrokerTelemetry)
    notifications: NotificationTelemetry = Field(default_factory=NotificationTelemetry)


class OperationalReliabilityTracker:
    """Tracks and persists real-time operational health and execution telemetry."""

    def __init__(self, log_dir: Optional[Path] = None, symbol: str = "ETHUSDT"):
        self.log_dir = log_dir or (settings.research_dir / "audit" / "reliability")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.symbol = symbol

        self.market_data = MarketDataTelemetry()
        self.signal_engine = SignalEngineTelemetry()
        self.paper_broker = PaperBrokerTelemetry()
        self.notifications = NotificationTelemetry()

        self._reconnect_start_time: Optional[float] = None
        self._sent_notification_hashes: set = set()

    # --- Market Data Callbacks ---
    def record_ws_connected(self) -> None:
        self.market_data.websocket_connected = True
        if self._reconnect_start_time is not None:
            reconnect_dur = time.time() - self._reconnect_start_time
            self.market_data.total_reconnect_duration_seconds += reconnect_dur
            self._reconnect_start_time = None

    def record_ws_disconnected(self) -> None:
        self.market_data.websocket_connected = False
        self.market_data.reconnect_count += 1
        self._reconnect_start_time = time.time()

    def record_candle_received(self, latency_ms: int, is_duplicate: bool = False, is_stale: bool = False) -> None:
        self.market_data.total_messages_received += 1
        self.market_data.last_data_latency_ms = latency_ms
        if latency_ms > self.market_data.max_data_latency_ms:
            self.market_data.max_data_latency_ms = latency_ms
        if is_duplicate:
            self.market_data.duplicate_events_count += 1
        if is_stale:
            self.market_data.stale_data_events_count += 1

    def record_rest_gap_recovery(self) -> None:
        self.market_data.rest_recovery_events_count += 1

    # --- Signal Engine Callbacks ---
    def record_evaluation(self, action: str, reason: Optional[str] = None) -> None:
        self.signal_engine.total_bar_evaluations += 1
        if action == "LONG":
            self.signal_engine.long_signals_generated += 1
        elif action == "SHORT":
            self.signal_engine.short_signals_generated += 1
        else:
            self.signal_engine.no_trade_decisions += 1
            if reason and "RISK" in reason.upper():
                self.signal_engine.risk_engine_rejections_count += 1

    def record_duplicate_signal_blocked(self) -> None:
        self.signal_engine.duplicate_signals_blocked += 1

    # --- Paper Broker Callbacks ---
    def record_trade_opened(self, fee: float, slippage: float) -> None:
        self.paper_broker.simulated_entries_count += 1
        self.paper_broker.total_fees_debited += fee
        self.paper_broker.total_slippage_incurred += slippage

    def record_trade_closed(self, exit_reason: str, fee: float) -> None:
        if "PROFIT" in exit_reason.upper():
            self.paper_broker.take_profit_events_count += 1
        else:
            self.paper_broker.stop_loss_events_count += 1
        self.paper_broker.total_fees_debited += fee

    # --- Notification Callbacks ---
    def is_notification_duplicate(self, text_hash: str) -> bool:
        if text_hash in self._sent_notification_hashes:
            self.notifications.duplicate_notifications_blocked += 1
            return True
        self._sent_notification_hashes.add(text_hash)
        return False

    def record_notification_result(self, success: bool, latency_ms: float = 0.0) -> None:
        if success:
            self.notifications.telegram_dispatches_success += 1
        else:
            self.notifications.telegram_dispatches_failed += 1
        
        total = self.notifications.telegram_dispatches_success + self.notifications.telegram_dispatches_failed
        prev_avg = self.notifications.average_dispatch_latency_ms
        self.notifications.average_dispatch_latency_ms = ((prev_avg * (total - 1)) + latency_ms) / max(1, total)

    # --- Persistence ---
    def checkpoint_daily_telemetry(self, timestamp_ms: Optional[int] = None) -> DailyReliabilityRecord:
        """Write consolidated daily telemetry record to jsonl."""
        now_ms = timestamp_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
        dt_str = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        date_str = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

        record = DailyReliabilityRecord(
            timestamp_ms=now_ms,
            datetime_utc=dt_str,
            symbol=self.symbol,
            market_data=self.market_data.model_copy(),
            signal_engine=self.signal_engine.model_copy(),
            paper_broker=self.paper_broker.model_copy(),
            notifications=self.notifications.model_copy(),
        )

        file_path = self.log_dir / f"reliability_{date_str}.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump()) + "\n")

        return record
