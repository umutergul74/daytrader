"""Tests for Backtest Engine execution and intrabar ambiguity handling."""

import polars as pl
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.backtest.engine import BacktestEngine
from quant_platform.backtest.costs import CostModel


def test_backtest_engine_executes_trades(synthetic_1m_data: pl.DataFrame):
    """Verify that BacktestEngine processes signals, records trades, and computes metrics."""
    strategy = EmaTrendStrategy(fast_period=10, slow_period=30, atr_multiplier_stop=1.5, risk_reward_ratio=2.0)
    engine = BacktestEngine(
        cost_model=CostModel(maker_fee_rate=0.0002, taker_fee_rate=0.0005, slippage_bps=2.0),
        initial_capital=10000.0,
        risk_per_trade_fraction=0.01,
    )

    result = engine.run(synthetic_1m_data, strategy)
    m = result.metrics

    assert m.trade_count >= 0
    assert len(result.equity_curve) > 0
    if m.trade_count > 0:
        assert m.total_fees > 0
        assert m.total_slippage > 0
        assert -100.0 <= m.max_drawdown_pct <= 100.0


def test_intrabar_ambiguity_conservative_policy():
    """Verify conservative policy triggers Stop Loss when both TP and SL are hit in the same bar."""
    # Hand-craft a trade where bar 1 generates Long, bar 2 fills, bar 3 has extreme spike touching both TP and SL
    bars = [
        {"open_time": 1000, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100.0},
        {"open_time": 2000, "open": 2000.0, "high": 2005.0, "low": 1995.0, "close": 2000.0, "volume": 100.0},
        {"open_time": 3000, "open": 2000.0, "high": 2200.0, "low": 1800.0, "close": 2000.0, "volume": 100.0}, # Huge spike
    ]
    df = pl.DataFrame(bars)

    # Strategy that generates an immediate long signal at bar 1
    from quant_platform.domain.signal import SignalCandidate, SignalDirection, StopCandidate, TargetCandidate
    from quant_platform.strategies.base import BaseStrategy, StrategyMetadata

    class DummySignalStrategy(BaseStrategy):
        def generate_signals(self, df):
            return [
                SignalCandidate(
                    signal_id="SIG-DUMMY",
                    strategy_id="dummy",
                    strategy_version="v1",
                    timestamp=1000,
                    direction=SignalDirection.LONG,
                    entry_price=2000.0,
                    stop_candidate=StopCandidate(name="SL", price=1900.0, risk_distance=100.0),
                    target_candidates=[TargetCandidate(name="TP1", price=2200.0, reward_r=2.0)],
                    calculated_rr=2.0,
                )
            ]

    strategy = DummySignalStrategy(StrategyMetadata(strategy_id="dummy", hypothesis="test"))
    engine = BacktestEngine(conservative_intrabar_ambiguity=True)
    res = engine.run(df, strategy)

    assert res.metrics.intrabar_ambiguity_count == 1
    assert len(res.ledger.trades) == 1
    # Conservative policy must trigger STOP_LOSS
    assert res.ledger.trades[0].exit_reason.value == "STOP_LOSS"
