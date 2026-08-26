"""Historical Out-of-Sample (OOS) vs Live Shadow Expectation Monitor.

Compares live operational trade frequencies, win rates, expectancies, and rejection
reasons against empirical historical baselines to detect structural edge decay or divergence.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from quant_platform.live.paper_broker import PaperPortfolio, TradeRecord
from quant_platform.observability.logger import logger


class HistoricalExpectationBaseline(BaseModel):
    """Historical out-of-sample benchmark expectations for a strategy."""
    strategy_id: str
    expected_trade_frequency_per_1000_bars: float = 12.0
    expected_win_rate_pct: float = 45.0
    expected_profit_factor: float = 1.80
    expected_average_r: float = 0.45
    expected_long_short_ratio: float = 1.10
    expected_max_drawdown_pct: float = 6.50


class ExpectationComparisonReport(BaseModel):
    """Comparison matrix between Historical OOS expectations and Live Shadow reality."""
    strategy_id: str
    bars_monitored: int
    live_trades_count: int
    historical_trade_frequency: float
    live_trade_frequency_per_1000_bars: float
    frequency_divergence_ratio: float
    historical_win_rate_pct: float
    live_win_rate_pct: float
    win_rate_delta: float
    historical_profit_factor: float
    live_profit_factor: float
    profit_factor_delta: float
    live_average_r: float
    rejection_reason_breakdown: Dict[str, int] = Field(default_factory=dict)
    has_material_divergence: bool = False
    divergence_warnings: List[str] = Field(default_factory=list)


class ExpectationMonitor:
    """Monitors live trade behavior against frozen historical expectations."""

    def __init__(
        self,
        strategy_id: str,
        baseline: Optional[HistoricalExpectationBaseline] = None,
    ):
        self.strategy_id = strategy_id
        self.baseline = baseline or HistoricalExpectationBaseline(strategy_id=strategy_id)
        self.total_bars_evaluated: int = 0
        self.rejection_counts: Dict[str, int] = {}

    def record_bar_decision(self, action: str, reason: Optional[str] = None) -> None:
        """Record evaluation decision and reason counts."""
        self.total_bars_evaluated += 1
        if action == "NO_TRADE" and reason:
            self.rejection_counts[reason] = self.rejection_counts.get(reason, 0) + 1

    def generate_report(self, portfolio: PaperPortfolio) -> ExpectationComparisonReport:
        """Generate structured comparison report between live performance and historical expectation."""
        total_trades = portfolio.total_trades_count
        bars = max(1, self.total_bars_evaluated)
        live_freq = (total_trades / bars) * 1000.0
        freq_div_ratio = live_freq / max(0.01, self.baseline.expected_trade_frequency_per_1000_bars)

        live_wr = (portfolio.profitable_trades_count / max(1, total_trades)) * 100.0
        wr_delta = live_wr - self.baseline.expected_win_rate_pct

        gross_win = sum(t.net_pnl for t in portfolio.closed_trades if t.net_pnl > 0)
        gross_loss = abs(sum(t.net_pnl for t in portfolio.closed_trades if t.net_pnl < 0))
        live_pf = (gross_win / max(0.01, gross_loss)) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0)
        pf_delta = live_pf - self.baseline.expected_profit_factor

        live_avg_r = (sum(t.r_multiple for t in portfolio.closed_trades) / max(1, total_trades)) if total_trades > 0 else 0.0

        warnings = []
        has_divergence = False

        if bars >= 200:
            if freq_div_ratio < 0.30:
                has_divergence = True
                warnings.append(f"TRADE_STARVATION: Live frequency ({live_freq:.1f}/1000 bars) is <30% of expected ({self.baseline.expected_trade_frequency_per_1000_bars:.1f}).")
            elif freq_div_ratio > 3.0:
                has_divergence = True
                warnings.append(f"OVERTRADING: Live frequency ({live_freq:.1f}/1000 bars) is >300% of expected ({self.baseline.expected_trade_frequency_per_1000_bars:.1f}).")

            if total_trades >= 15 and live_pf < 0.80:
                has_divergence = True
                warnings.append(f"PROFIT_FACTOR_DECAY: Live PF ({live_pf:.2f}) is significantly below historical ({self.baseline.expected_profit_factor:.2f}).")

        return ExpectationComparisonReport(
            strategy_id=self.strategy_id,
            bars_monitored=bars,
            live_trades_count=total_trades,
            historical_trade_frequency=self.baseline.expected_trade_frequency_per_1000_bars,
            live_trade_frequency_per_1000_bars=live_freq,
            frequency_divergence_ratio=freq_div_ratio,
            historical_win_rate_pct=self.baseline.expected_win_rate_pct,
            live_win_rate_pct=live_wr,
            win_rate_delta=wr_delta,
            historical_profit_factor=self.baseline.expected_profit_factor,
            live_profit_factor=live_pf,
            profit_factor_delta=pf_delta,
            live_average_r=live_avg_r,
            rejection_reason_breakdown=dict(sorted(self.rejection_counts.items(), key=lambda item: item[1], reverse=True)),
            has_material_divergence=has_divergence,
            divergence_warnings=warnings,
        )
