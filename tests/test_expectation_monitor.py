"""Tests for Live Expectation Monitor."""

from quant_platform.live.expectation_monitor import ExpectationMonitor, HistoricalExpectationBaseline
from quant_platform.live.paper_broker import PaperPortfolio, TradeRecord
from quant_platform.domain.trade import PositionSide, ExitReason


def test_expectation_monitor_comparison():
    """Verify comparing live trade metrics against historical baseline expectations."""
    baseline = HistoricalExpectationBaseline(
        strategy_id="test_strat",
        expected_trade_frequency_per_1000_bars=10.0,
        expected_win_rate_pct=50.0,
        expected_profit_factor=2.0,
    )

    monitor = ExpectationMonitor(strategy_id="test_strat", baseline=baseline)

    for _ in range(500):
        monitor.record_bar_decision(action="NO_TRADE", reason="REGIME_FILTER")

    portfolio = PaperPortfolio(
        total_trades_count=5,
        profitable_trades_count=3,
        total_net_pnl=150.0,
        closed_trades=[
            TradeRecord(
                trade_id="T1", signal_id="S1", strategy_id="test_strat", symbol="ETHUSDT",
                side=PositionSide.LONG, entry_time=1000, exit_time=2000, entry_price=2000.0,
                exit_price=2050.0, quantity=1.0, notional_entry=2000.0, notional_exit=2050.0,
                fee_paid=2.0, slippage_paid=0.0, funding_paid=0.0, gross_pnl=50.0, net_pnl=48.0,
                pnl_percent=2.4, r_multiple=1.5, exit_reason=ExitReason.TAKE_PROFIT, holding_period_minutes=15.0,
            ),
        ],
    )

    report = monitor.generate_report(portfolio)
    assert report.bars_monitored == 500
    assert report.live_trades_count == 5
    assert report.live_win_rate_pct == 60.0
    assert report.rejection_reason_breakdown.get("REGIME_FILTER") == 500
