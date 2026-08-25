"""Comprehensive Strategy Robustness Suite."""

from typing import Dict, List, Any, Optional
import numpy as np
from pydantic import BaseModel, Field
import polars as pl

from quant_platform.strategies.base import BaseStrategy
from quant_platform.backtest.engine import BacktestEngine, BacktestResult
from quant_platform.backtest.costs import CostModel
from quant_platform.observability.logger import logger


class RobustnessReport(BaseModel):
    """Result of systematic robustness and stress testing."""
    strategy_id: str
    baseline_return: float
    fee_sensitivity: Dict[str, float]
    slippage_sensitivity: Dict[str, float]
    top_trades_concentration_pct: Dict[str, float]
    monte_carlo_drawdown_95th: float
    is_robust_to_costs: bool
    summary: str


class RobustnessEngine:
    """Stress tests strategy results under adverse cost, slippage, parameter, and sequencing conditions."""

    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital

    def run_robustness_suite(
        self,
        df: pl.DataFrame,
        strategy: BaseStrategy,
        base_cost: Optional[CostModel] = None,
    ) -> RobustnessReport:
        """Run standard stress tests: cost sensitivity, trade concentration, and Monte Carlo."""
        cost = base_cost or CostModel(maker_fee_rate=0.0002, taker_fee_rate=0.0005, slippage_bps=2.0)
        base_engine = BacktestEngine(cost_model=cost, initial_capital=self.initial_capital)

        # 1. Baseline
        base_res = base_engine.run(df, strategy)
        base_ret = base_res.metrics.total_net_return
        trades = base_res.ledger.trades

        # 2. Fee Sensitivity (+25%, +50%)
        fee_results = {}
        for fee_mult, label in [(1.25, "+25%"), (1.50, "+50%")]:
            adj_cost = CostModel(
                maker_fee_rate=cost.maker_fee_rate * fee_mult,
                taker_fee_rate=cost.taker_fee_rate * fee_mult,
                slippage_bps=cost.slippage_bps,
            )
            eng = BacktestEngine(cost_model=adj_cost, initial_capital=self.initial_capital)
            res = eng.run(df, strategy)
            fee_results[label] = res.metrics.total_net_return

        # 3. Slippage Sensitivity (+50%, +100%)
        slip_results = {}
        for slip_mult, label in [(1.5, "+50%"), (2.0, "+100%")]:
            adj_cost = CostModel(
                maker_fee_rate=cost.maker_fee_rate,
                taker_fee_rate=cost.taker_fee_rate,
                slippage_bps=cost.slippage_bps * slip_mult,
            )
            eng = BacktestEngine(cost_model=adj_cost, initial_capital=self.initial_capital)
            res = eng.run(df, strategy)
            slip_results[label] = res.metrics.total_net_return

        # 4. Trade Concentration Analysis
        concentration = {}
        if trades:
            pnls = sorted([t.net_pnl for t in trades], reverse=True)
            total_profit = sum(p for p in pnls if p > 0)
            if total_profit > 0:
                top1 = pnls[0] / total_profit * 100.0 if len(pnls) >= 1 else 0.0
                top5 = sum(pnls[:5]) / total_profit * 100.0 if len(pnls) >= 5 else 100.0
                concentration["top_1_trade_profit_pct"] = float(top1)
                concentration["top_5_trades_profit_pct"] = float(top5)
            else:
                concentration["top_1_trade_profit_pct"] = 0.0
                concentration["top_5_trades_profit_pct"] = 0.0
        else:
            concentration["top_1_trade_profit_pct"] = 0.0
            concentration["top_5_trades_profit_pct"] = 0.0

        # 5. Monte Carlo Reshuffling (100 resamples of trade sequences)
        mc_max_dds = []
        if len(trades) > 1:
            trade_pnls = np.array([t.net_pnl for t in trades])
            for _ in range(100):
                shuffled_pnl = np.random.permutation(trade_pnls)
                equity = self.initial_capital + np.cumsum(shuffled_pnl)
                peak = np.maximum.accumulate(equity)
                dd = (peak - equity) / peak * 100.0
                mc_max_dds.append(np.max(dd))
            mc_95th = float(np.percentile(mc_max_dds, 95))
        else:
            mc_95th = 0.0

        is_robust = fee_results.get("+50%", -1.0) > 0 and slip_results.get("+100%", -1.0) > 0 if base_ret > 0 else False

        summary = (
            f"Robustness Report for {strategy.metadata.strategy_id}:\n"
            f" - Baseline Net Return: {base_ret:+.2f}%\n"
            f" - Return at +50% Fees: {fee_results.get('+50%', 0.0):+.2f}%\n"
            f" - Return at +100% Slippage: {slip_results.get('+100%', 0.0):+.2f}%\n"
            f" - Top 1 Trade Profit Concentration: {concentration.get('top_1_trade_profit_pct', 0.0):.1f}%\n"
            f" - Monte Carlo 95th Percentile Max Drawdown: {mc_95th:.2f}%\n"
            f" - Verdict: {'ROBUST' if is_robust else 'SENSITIVE / CONDITIONAL'}"
        )

        return RobustnessReport(
            strategy_id=strategy.metadata.strategy_id,
            baseline_return=base_ret,
            fee_sensitivity=fee_results,
            slippage_sensitivity=slip_results,
            top_trades_concentration_pct=concentration,
            monte_carlo_drawdown_95th=mc_95th,
            is_robust_to_costs=is_robust,
            summary=summary,
        )
