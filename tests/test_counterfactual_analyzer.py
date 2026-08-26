"""Tests for Counterfactual Shadow Filter Evaluation Engine."""

from quant_platform.research.counterfactual_analyzer import CounterfactualAnalyzer


def test_counterfactual_analyzer_suite():
    """Verify evaluating counterfactual filters on trade datasets."""
    trades = [
        {"net_pnl": 100.0, "r_multiple": 2.0, "direction": "LONG", "cvd_bullish_divergence": True, "joint_price_oi_regime": "LONG_BUILDUP", "trade_imbalance_1m": 0.20, "is_liquidation_burst": True},
        {"net_pnl": -50.0, "r_multiple": -1.0, "direction": "LONG", "cvd_bullish_divergence": False, "joint_price_oi_regime": "LONG_LIQUIDATION", "trade_imbalance_1m": -0.10, "is_liquidation_burst": False},
        {"net_pnl": 80.0, "r_multiple": 1.6, "direction": "SHORT", "cvd_bearish_divergence": True, "joint_price_oi_regime": "SHORT_BUILDUP", "trade_imbalance_1m": -0.15, "is_liquidation_burst": True},
        {"net_pnl": -50.0, "r_multiple": -1.0, "direction": "SHORT", "cvd_bearish_divergence": False, "joint_price_oi_regime": "SHORT_COVERING", "trade_imbalance_1m": 0.10, "is_liquidation_burst": False},
    ] * 5

    study = CounterfactualAnalyzer.run_standard_counterfactual_suite(
        strategy_id="test_strat",
        trades_with_features=trades,
    )

    assert study.total_trades_analyzed == 20
    assert study.baseline_win_rate == 50.0
    assert len(study.filter_evaluations) == 4

    # CVD Divergence filter should filter out the 10 losing trades
    cvd_eval = next(f for f in study.filter_evaluations if f.filter_name == "CVD_DIVERGENCE_REQUIRED")
    assert cvd_eval.filtered_trade_count == 10
    assert cvd_eval.filtered_win_rate == 100.0
    assert cvd_eval.marginal_edge_status == "ACCEPT"
