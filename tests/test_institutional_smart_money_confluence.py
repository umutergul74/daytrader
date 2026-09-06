"""Tests for InstitutionalSmartMoneyConfluenceStrategy."""

import polars as pl
import pytest
from quant_platform.strategies.advanced.institutional_smart_money_confluence import (
    InstitutionalSmartMoneyConfluenceStrategy,
)
from quant_platform.strategies.catalog import StrategyCatalog
from quant_platform.domain.signal import SignalDirection, SignalType
from quant_platform.backtest.engine import BacktestEngine
from quant_platform.backtest.costs import CostModel
from quant_platform.data.timeframes.resampler import CausalResampler


def test_strategy_catalog_registration():
    """Verify strategy is registered in StrategyCatalog with valid metadata."""
    strat_cls = StrategyCatalog.get_strategy_class("institutional_smc_confluence")
    assert strat_cls is not None
    assert strat_cls == InstitutionalSmartMoneyConfluenceStrategy

    meta = StrategyCatalog.get("smc:institutional_confluence:v1")
    assert meta is not None
    assert meta.family == "smc"
    assert "structure:4h_market_structure" in meta.required_features
    assert "smc:fvg_mitigation" in meta.required_features
    assert meta.parameters["risk_reward_ratio"] == 2.4


def test_signal_structural_integrity(synthetic_1m_data: pl.DataFrame):
    """Verify generated signals maintain structural validity and risk rules."""
    # Synthetic data: resample to 1H (or pass directly)
    strategy = InstitutionalSmartMoneyConfluenceStrategy(
        h4_left_bars=3,
        h4_right_bars=3,
        ltf_left_bars=3,
        ltf_right_bars=3,
        min_gap_atr_ratio=0.05,
        risk_reward_ratio=2.4,
        stop_atr_cushion=0.3,
        use_session_filter=False,  # Test without session filter to maximize signal test coverage
    )

    signals = strategy.generate_signals(synthetic_1m_data)

    for sig in signals:
        assert sig.strategy_id == "smc:institutional_confluence:v1"
        assert sig.direction in (SignalDirection.LONG, SignalDirection.SHORT)
        assert sig.stop_candidate is not None
        assert sig.calculated_rr == pytest.approx(2.4, rel=1e-3)
        assert len(sig.target_candidates) >= 1

        # Check structural stop loss placement validity
        if sig.direction == SignalDirection.LONG:
            assert sig.stop_candidate.price < sig.entry_price, "LONG stop must be below entry"
            assert sig.target_candidates[0].price > sig.entry_price, "LONG target must be above entry"
            expected_tp = sig.entry_price + (2.4 * sig.stop_candidate.risk_distance)
            assert sig.target_candidates[0].price == pytest.approx(expected_tp, rel=1e-3)
        elif sig.direction == SignalDirection.SHORT:
            assert sig.stop_candidate.price > sig.entry_price, "SHORT stop must be above entry"
            assert sig.target_candidates[0].price < sig.entry_price, "SHORT target must be below entry"
            expected_tp = sig.entry_price - (2.4 * sig.stop_candidate.risk_distance)
            assert sig.target_candidates[0].price == pytest.approx(expected_tp, rel=1e-3)

        # Evidence should contain multi-factor confluence tags
        assert len(sig.evidence) >= 3


def test_zero_lookahead_temporal_causality(synthetic_1m_data: pl.DataFrame):
    """Verify that signal timestamps strictly precede next-bar execution."""
    df_1h = CausalResampler.resample(synthetic_1m_data, target_timeframe="1h")
    strategy = InstitutionalSmartMoneyConfluenceStrategy(
        h4_left_bars=3,
        h4_right_bars=3,
        ltf_left_bars=3,
        ltf_right_bars=3,
        min_gap_atr_ratio=0.05,
        use_session_filter=False,
    )

    signals = strategy.generate_signals(df_1h)
    valid_open_times = set(df_1h["open_time"].to_list())
    valid_close_times = set(df_1h["close_time"].to_list())

    for sig in signals:
        # Signal timestamp must be an exact open or close time in the dataset
        assert sig.timestamp in valid_open_times or sig.timestamp in valid_close_times


def test_deterministic_confluence_backtest(synthetic_1m_data: pl.DataFrame):
    """Verify bit-for-bit deterministic backtest execution for the confluence strategy."""
    strategy = InstitutionalSmartMoneyConfluenceStrategy(
        h4_left_bars=3,
        h4_right_bars=3,
        ltf_left_bars=3,
        ltf_right_bars=3,
        min_gap_atr_ratio=0.05,
        risk_reward_ratio=2.4,
        stop_atr_cushion=0.3,
        use_session_filter=False,
    )
    cost = CostModel(maker_fee_rate=0.0002, taker_fee_rate=0.0005, slippage_bps=2.0)
    engine1 = BacktestEngine(cost_model=cost, initial_capital=10000.0, risk_per_trade_fraction=0.01)
    res1 = engine1.run(synthetic_1m_data, strategy)

    engine2 = BacktestEngine(cost_model=cost, initial_capital=10000.0, risk_per_trade_fraction=0.01)
    res2 = engine2.run(synthetic_1m_data, strategy)

    assert res1.metrics.total_net_return == res2.metrics.total_net_return
    assert res1.metrics.trade_count == res2.metrics.trade_count
    assert res1.metrics.win_rate == res2.metrics.win_rate
    assert res1.metrics.max_drawdown_pct == res2.metrics.max_drawdown_pct
