"""Performance analytics and quantitative metrics calculator."""

import math
from typing import List, Optional
import numpy as np
import polars as pl

from quant_platform.domain.experiment import QuantMetrics
from quant_platform.domain.trade import TradeRecord, PositionSide


class MetricCalculator:
    """Calculates rigorous quantitative trading metrics from TradeRecords."""

    @staticmethod
    def compute_metrics(
        trades: List[TradeRecord],
        initial_capital: float = 10000.0,
        total_bars: int = 1000,
        intrabar_ambiguity_count: int = 0,
    ) -> QuantMetrics:
        """Compute full statistical and financial performance metrics."""
        if not trades:
            return QuantMetrics(
                total_net_return=0.0,
                gross_return=0.0,
                total_fees=0.0,
                total_slippage=0.0,
                total_funding=0.0,
                trade_count=0,
                win_rate=0.0,
                average_winner=0.0,
                average_loser=0.0,
                payoff_ratio=0.0,
                expectancy=0.0,
                average_r=0.0,
                median_r=0.0,
                profit_factor=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_duration_bars=0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                exposure_pct=0.0,
                long_trades=0,
                short_trades=0,
                long_win_rate=0.0,
                short_win_rate=0.0,
                consecutive_wins_max=0,
                consecutive_losses_max=0,
                intrabar_ambiguity_count=intrabar_ambiguity_count,
            )

        n = len(trades)
        net_pnls = np.array([t.net_pnl for t in trades], dtype=np.float64)
        gross_pnls = np.array([t.gross_pnl for t in trades], dtype=np.float64)
        fees = np.array([t.fee_paid for t in trades], dtype=np.float64)
        slippage = np.array([t.slippage_paid for t in trades], dtype=np.float64)
        funding = np.array([t.funding_paid for t in trades], dtype=np.float64)
        r_multiples = np.array([t.r_multiple for t in trades], dtype=np.float64)

        total_net_pnl = float(net_pnls.sum())
        total_gross_pnl = float(gross_pnls.sum())
        total_fees = float(fees.sum())
        total_slippage = float(slippage.sum())
        total_funding = float(funding.sum())

        total_net_return_pct = (total_net_pnl / initial_capital) * 100.0
        gross_return_pct = (total_gross_pnl / initial_capital) * 100.0

        winners = net_pnls[net_pnls > 0]
        losers = net_pnls[net_pnls <= 0]
        win_count = len(winners)
        loss_count = len(losers)
        win_rate = (win_count / n) * 100.0 if n > 0 else 0.0

        avg_winner = float(winners.mean()) if win_count > 0 else 0.0
        avg_loser = float(losers.mean()) if loss_count > 0 else 0.0
        payoff_ratio = abs(avg_winner / avg_loser) if avg_loser != 0 else (avg_winner if avg_winner > 0 else 0.0)

        # Mathematical expectancy: (WinRate * AvgWin) - (LossRate * AvgLoss)
        win_prob = win_count / n
        loss_prob = loss_count / n
        expectancy = (win_prob * avg_winner) + (loss_prob * avg_loser)

        avg_r = float(r_multiples.mean()) if n > 0 else 0.0
        median_r = float(np.median(r_multiples)) if n > 0 else 0.0

        gross_profits = net_pnls[net_pnls > 0].sum()
        gross_losses = abs(net_pnls[net_pnls < 0].sum())
        profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.0 if gross_profits > 0 else 0.0)

        # Equity Curve and Max Drawdown calculation
        equity_curve = initial_capital + np.cumsum(net_pnls)
        peak = np.maximum.accumulate(equity_curve)
        drawdowns = (peak - equity_curve) / peak
        max_dd_pct = float(drawdowns.max() * 100.0) if len(drawdowns) > 0 else 0.0

        # Drawdown duration in trades
        max_dd_duration = 0
        current_dd_duration = 0
        for i in range(len(equity_curve)):
            if equity_curve[i] < peak[i]:
                current_dd_duration += 1
                if current_dd_duration > max_dd_duration:
                    max_dd_duration = current_dd_duration
            else:
                current_dd_duration = 0

        # Returns based Sharpe / Sortino
        returns_series = net_pnls / initial_capital
        std_ret = float(np.std(returns_series))
        mean_ret = float(np.mean(returns_series))
        sharpe = (mean_ret / (std_ret + 1e-12)) * np.sqrt(252.0) if std_ret > 0 else 0.0

        downside_returns = returns_series[returns_series < 0]
        downside_std = float(np.std(downside_returns)) if len(downside_returns) > 0 else 0.0
        sortino = (mean_ret / (downside_std + 1e-12)) * np.sqrt(252.0) if downside_std > 0 else 0.0

        calmar = (total_net_return_pct / (max_dd_pct + 1e-12)) if max_dd_pct > 0 else 0.0

        # Long vs Short breakdown
        long_trades = [t for t in trades if t.side == PositionSide.LONG]
        short_trades = [t for t in trades if t.side == PositionSide.SHORT]
        long_wins = [t for t in long_trades if t.net_pnl > 0]
        short_wins = [t for t in short_trades if t.net_pnl > 0]
        long_win_rate = (len(long_wins) / len(long_trades) * 100.0) if long_trades else 0.0
        short_win_rate = (len(short_wins) / len(short_trades) * 100.0) if short_trades else 0.0

        # Consecutive streaks
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        cur_wins = 0
        cur_losses = 0
        for pnl in net_pnls:
            if pnl > 0:
                cur_wins += 1
                cur_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, cur_wins)
            else:
                cur_losses += 1
                cur_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, cur_losses)

        # Market exposure
        total_holding_minutes = sum(t.holding_period_minutes for t in trades)
        total_minutes = total_bars * 1.0  # approximate on 1m
        exposure_pct = min(100.0, (total_holding_minutes / max(1.0, total_minutes)) * 100.0)

        return QuantMetrics(
            total_net_return=round(total_net_return_pct, 3),
            gross_return=round(gross_return_pct, 3),
            total_fees=round(total_fees, 2),
            total_slippage=round(total_slippage, 2),
            total_funding=round(total_funding, 2),
            trade_count=n,
            win_rate=round(win_rate, 2),
            average_winner=round(avg_winner, 2),
            average_loser=round(avg_loser, 2),
            payoff_ratio=round(payoff_ratio, 2),
            expectancy=round(expectancy, 2),
            average_r=round(avg_r, 3),
            median_r=round(median_r, 3),
            profit_factor=round(profit_factor, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            max_drawdown_duration_bars=max_dd_duration,
            sharpe_ratio=round(sharpe, 3),
            sortino_ratio=round(sortino, 3),
            calmar_ratio=round(calmar, 3),
            exposure_pct=round(exposure_pct, 2),
            long_trades=len(long_trades),
            short_trades=len(short_trades),
            long_win_rate=round(long_win_rate, 2),
            short_win_rate=round(short_win_rate, 2),
            consecutive_wins_max=max_consecutive_wins,
            consecutive_losses_max=max_consecutive_losses,
            intrabar_ambiguity_count=intrabar_ambiguity_count,
        )
