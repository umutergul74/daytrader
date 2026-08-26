"""Tests for Operational Reliability Tracker."""

import tempfile
from pathlib import Path
from quant_platform.live.reliability import OperationalReliabilityTracker


def test_reliability_tracker_lifecycle_and_persistence():
    """Verify recording telemetry across all subsystems and checkpointing to jsonl."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tracker = OperationalReliabilityTracker(log_dir=tmp_path, symbol="ETHUSDT")

        # 1. Market data events
        tracker.record_ws_connected()
        tracker.record_candle_received(latency_ms=120)
        tracker.record_candle_received(latency_ms=150, is_duplicate=True)
        tracker.record_ws_disconnected()
        tracker.record_ws_connected()
        tracker.record_rest_gap_recovery()

        # 2. Signal engine events
        tracker.record_evaluation(action="LONG")
        tracker.record_evaluation(action="SHORT")
        tracker.record_evaluation(action="NO_TRADE", reason="RISK_INSUFFICIENT_RR")
        tracker.record_duplicate_signal_blocked()

        # 3. Paper broker events
        tracker.record_trade_opened(fee=1.50, slippage=0.40)
        tracker.record_trade_closed(exit_reason="TAKE_PROFIT_1", fee=1.50)

        # 4. Notification events
        assert tracker.is_notification_duplicate("hash_1") is False
        assert tracker.is_notification_duplicate("hash_1") is True
        tracker.record_notification_result(success=True, latency_ms=45.0)

        # 5. Checkpoint
        record = tracker.checkpoint_daily_telemetry()
        assert record.market_data.total_messages_received == 2
        assert record.market_data.duplicate_events_count == 1
        assert record.signal_engine.total_bar_evaluations == 3
        assert record.signal_engine.risk_engine_rejections_count == 1
        assert record.paper_broker.simulated_entries_count == 1
        assert record.paper_broker.take_profit_events_count == 1
        assert record.notifications.duplicate_notifications_blocked == 1

        jsonl_files = list(tmp_path.glob("reliability_*.jsonl"))
        assert len(jsonl_files) == 1
