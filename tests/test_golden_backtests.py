"""Golden deterministic backtest regression test."""

import polars as pl
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.backtest.engine import BacktestEngine
from quant_platform.backtest.costs import CostModel


def test_deterministic_golden_backtest_run(synthetic_1m_data: pl.DataFrame):
    """Ensure identical inputs produce bit-for-bit deterministic backtest metrics."""
    strategy = EmaTrendStrategy(fast_period=20, slow_period=50, atr_multiplier_stop=2.0, risk_reward_ratio=2.0)
    cost = CostModel(maker_fee_rate=0.0002, taker_fee_rate=0.0005, slippage_bps=2.0)

    engine1 = BacktestEngine(cost_model=cost, initial_capital=10000.0, risk_per_trade_fraction=0.01)
    res1 = engine1.run(synthetic_1m_data, strategy)

    engine2 = BacktestEngine(cost_model=cost, initial_capital=10000.0, risk_per_trade_fraction=0.01)
    res2 = engine2.run(synthetic_1m_data, strategy)

    assert res1.metrics.total_net_return == res2.metrics.total_net_return
    assert res1.metrics.trade_count == res2.metrics.trade_count
    assert res1.metrics.win_rate == res2.metrics.win_rate
    assert res1.metrics.sharpe_ratio == res2.metrics.sharpe_ratio
    assert res1.metrics.max_drawdown_pct == res2.metrics.max_drawdown_pct
