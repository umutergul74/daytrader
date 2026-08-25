"""Tests for Decision Logging and Drift Monitoring."""

from pathlib import Path
import pytest
from quant_platform.live.decision_logger import DecisionLogger
from quant_platform.live.drift_monitor import DriftMonitor


def test_decision_logger_writes_jsonl(tmp_path: Path):
    """Verify decision logger creates structured jsonl log records."""
    logger = DecisionLogger(log_dir=tmp_path)

    rec = logger.log_decision(
        timestamp_ms=1704067200000,
        symbol="ETHUSDT",
        strategy_id="test_strat",
        action="NO_TRADE",
        reason="REGIME_MISMATCH",
        market_regime="COMPRESSION",
        current_price=2500.0,
    )

    assert rec.action == "NO_TRADE"
    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1
    content = log_files[0].read_text(encoding="utf-8")
    assert "REGIME_MISMATCH" in content


def test_drift_monitor_starvation_alert():
    """Verify drift monitor flags low signal frequency starvation alert."""
    monitor = DriftMonitor(strategy_id="test_strat", expected_trade_frequency_per_100_bars=2.0)

    # 100 bars with 0 signals -> drift ratio 0.0 < 0.25
    for _ in range(100):
        monitor.record_bar_evaluation(is_signal_triggered=False)

    status = monitor.check_drift()
    assert status.has_drift_alert is True
    assert "STARVATION DRIFT" in status.drift_alert_message
