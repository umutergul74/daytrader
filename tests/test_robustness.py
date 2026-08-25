"""Tests for Robustness Suite and Stress Testing."""

import polars as pl
import pytest
from quant_platform.research.robustness import RobustnessEngine
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy


def test_robustness_suite_cost_and_concentration(synthetic_1m_data: pl.DataFrame):
    """Verify that robustness engine calculates fee/slippage sensitivity and concentration."""
    rob_engine = RobustnessEngine(initial_capital=10000.0)
    strategy = EmaTrendStrategy(fast_period=10, slow_period=20)

    report = rob_engine.run_robustness_suite(synthetic_1m_data, strategy)

    assert "+25%" in report.fee_sensitivity
    assert "+50%" in report.fee_sensitivity
    assert "+50%" in report.slippage_sensitivity
    assert "top_1_trade_profit_pct" in report.top_trades_concentration_pct
    assert isinstance(report.monte_carlo_drawdown_95th, float)
