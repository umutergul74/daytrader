"""Event-aware Backtesting Engine."""

from typing import List, Optional, Dict, Any
import polars as pl

from quant_platform.domain.signal import SignalCandidate, SignalDirection
from quant_platform.domain.trade import PositionSide, ExitReason, TradeRecord
from quant_platform.domain.experiment import QuantMetrics
from quant_platform.strategies.base import BaseStrategy
from quant_platform.risk.engine import RiskEngine, RiskDecision
from quant_platform.risk.sizing import PositionSizer
from quant_platform.backtest.costs import CostModel
from quant_platform.backtest.ledger import TradeLedger
from quant_platform.backtest.metrics import MetricCalculator
from quant_platform.observability.logger import logger


class BacktestResult:
    """Encapsulates output of a backtest run."""
    def __init__(self, ledger: TradeLedger, metrics: QuantMetrics, equity_curve: pl.DataFrame):
        self.ledger = ledger
        self.metrics = metrics
        self.equity_curve = equity_curve


class BacktestEngine:
    """Event-aware causal backtest execution engine."""

    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        risk_engine: Optional[RiskEngine] = None,
        position_sizer: Optional[PositionSizer] = None,
        initial_capital: float = 10000.0,
        risk_per_trade_fraction: float = 0.01,
        conservative_intrabar_ambiguity: bool = True,
    ):
        self.cost_model = cost_model or CostModel()
        self.risk_engine = risk_engine or RiskEngine()
        self.position_sizer = position_sizer or PositionSizer()
        self.initial_capital = initial_capital
        self.risk_per_trade_fraction = risk_per_trade_fraction
        self.conservative_intrabar_ambiguity = conservative_intrabar_ambiguity

    def run(self, df: pl.DataFrame, strategy: BaseStrategy) -> BacktestResult:
        """Run backtest causal simulation over DataFrame with given strategy."""
        if df.is_empty():
            raise ValueError("Input DataFrame is empty.")

        # 1. Generate candidate signals
        raw_signals = strategy.generate_signals(df)
        signals_by_ts: Dict[int, SignalCandidate] = {s.timestamp: s for s in raw_signals}

        ledger = TradeLedger()
        current_equity = self.initial_capital
        intrabar_ambiguity_count = 0

        # State tracking
        in_position = False
        pos_side: Optional[PositionSide] = None
        pos_qty: float = 0.0
        pos_entry_price: float = 0.0
        pos_stop_price: float = 0.0
        pos_target_price: float = 0.0
        pos_entry_time: int = 0
        pos_signal_id: str = ""
        pos_risk_usdt: float = 0.0
        pos_entry_fees: float = 0.0
        pos_entry_slippage: float = 0.0
        pos_bars_held: int = 0
        max_favorable_price: float = 0.0
        max_adverse_price: float = 0.0

        rows = df.iter_rows(named=True)
        pending_signal: Optional[SignalCandidate] = None

        for i, bar in enumerate(rows):
            curr_time = int(bar["open_time"])
            open_p = float(bar["open"])
            high_p = float(bar["high"])
            low_p = float(bar["low"])
            close_p = float(bar["close"])

            # ----------------------------------------------------
            # 1. Execute Pending Signal at Open of this bar (t+1)
            # ----------------------------------------------------
            if pending_signal is not None and not in_position:
                risk_decision = self.risk_engine.evaluate_signal(pending_signal)
                if risk_decision.is_approved:
                    side = PositionSide.LONG if pending_signal.direction == SignalDirection.LONG else PositionSide.SHORT
                    stop_p = risk_decision.adjusted_stop_price
                    tp_p = risk_decision.adjusted_target_price

                    sizing = self.position_sizer.size_fixed_risk(
                        equity=current_equity,
                        entry_price=open_p,
                        stop_price=stop_p,
                        risk_fraction=self.risk_per_trade_fraction,
                    )

                    if sizing.is_valid and sizing.quantity > 0:
                        fill_p, slip, fee = self.cost_model.calculate_entry_fill(
                            price=open_p,
                            is_taker=True,
                            is_long=(side == PositionSide.LONG),
                        )
                        in_position = True
                        pos_side = side
                        pos_qty = sizing.quantity
                        pos_entry_price = fill_p
                        pos_stop_price = stop_p
                        pos_target_price = tp_p
                        pos_entry_time = curr_time
                        pos_signal_id = pending_signal.signal_id
                        pos_risk_usdt = sizing.risk_amount_usdt
                        pos_entry_fees = fee * pos_qty
                        pos_entry_slippage = slip * pos_qty
                        pos_bars_held = 0
                        max_favorable_price = fill_p
                        max_adverse_price = fill_p

                pending_signal = None

            # ----------------------------------------------------
            # 2. Evaluate Active Position Intrabar
            # ----------------------------------------------------
            if in_position:
                pos_bars_held += 1
                exit_triggered = False
                exit_reason: Optional[ExitReason] = None
                raw_exit_price: float = 0.0
                is_exit_taker = True

                if pos_side == PositionSide.LONG:
                    max_favorable_price = max(max_favorable_price, high_p)
                    max_adverse_price = min(max_adverse_price, low_p)

                    sl_hit = low_p <= pos_stop_price
                    tp_hit = high_p >= pos_target_price

                    # Intrabar ambiguity handling
                    if sl_hit and tp_hit:
                        intrabar_ambiguity_count += 1
                        if self.conservative_intrabar_ambiguity:
                            exit_triggered = True
                            exit_reason = ExitReason.STOP_LOSS
                            raw_exit_price = pos_stop_price
                        else:
                            exit_triggered = True
                            exit_reason = ExitReason.TAKE_PROFIT
                            raw_exit_price = pos_target_price
                            is_exit_taker = False
                    elif sl_hit:
                        exit_triggered = True
                        exit_reason = ExitReason.STOP_LOSS
                        raw_exit_price = pos_stop_price
                    elif tp_hit:
                        exit_triggered = True
                        exit_reason = ExitReason.TAKE_PROFIT
                        raw_exit_price = pos_target_price
                        is_exit_taker = False  # Limit exit

                elif pos_side == PositionSide.SHORT:
                    max_favorable_price = min(max_favorable_price, low_p)
                    max_adverse_price = max(max_adverse_price, high_p)

                    sl_hit = high_p >= pos_stop_price
                    tp_hit = low_p <= pos_target_price

                    if sl_hit and tp_hit:
                        intrabar_ambiguity_count += 1
                        if self.conservative_intrabar_ambiguity:
                            exit_triggered = True
                            exit_reason = ExitReason.STOP_LOSS
                            raw_exit_price = pos_stop_price
                        else:
                            exit_triggered = True
                            exit_reason = ExitReason.TAKE_PROFIT
                            raw_exit_price = pos_target_price
                            is_exit_taker = False
                    elif sl_hit:
                        exit_triggered = True
                        exit_reason = ExitReason.STOP_LOSS
                        raw_exit_price = pos_stop_price
                    elif tp_hit:
                        exit_triggered = True
                        exit_reason = ExitReason.TAKE_PROFIT
                        raw_exit_price = pos_target_price
                        is_exit_taker = False

                # Max holding time expiry
                if not exit_triggered and pos_bars_held >= self.risk_engine.max_holding_bars:
                    exit_triggered = True
                    exit_reason = ExitReason.MAX_HOLDING_TIME
                    raw_exit_price = close_p
                    is_exit_taker = True

                # Process Exit
                if exit_triggered:
                    exit_fill_p, exit_slip, exit_fee = self.cost_model.calculate_exit_fill(
                        price=raw_exit_price,
                        is_taker=is_exit_taker,
                        is_long=(pos_side == PositionSide.LONG),
                    )
                    total_fee = pos_entry_fees + (exit_fee * pos_qty)
                    total_slip = pos_entry_slippage + (exit_slip * pos_qty)

                    if pos_side == PositionSide.LONG:
                        gross_pnl = (exit_fill_p - pos_entry_price) * pos_qty
                        mfe = (max_favorable_price - pos_entry_price) / pos_entry_price * 100.0
                        mae = (pos_entry_price - max_adverse_price) / pos_entry_price * 100.0
                    else:
                        gross_pnl = (pos_entry_price - exit_fill_p) * pos_qty
                        mfe = (pos_entry_price - max_favorable_price) / pos_entry_price * 100.0
                        mae = (max_adverse_price - pos_entry_price) / pos_entry_price * 100.0

                    net_pnl = gross_pnl - total_fee
                    r_mult = net_pnl / (pos_risk_usdt + 1e-12)

                    trade = TradeRecord(
                        trade_id=f"TRD-{pos_entry_time}-{len(ledger.trades)+1}",
                        signal_id=pos_signal_id,
                        strategy_id=strategy.metadata.strategy_id,
                        symbol="ETHUSDT",
                        side=pos_side,
                        entry_time=pos_entry_time,
                        exit_time=curr_time,
                        entry_price=round(pos_entry_price, 2),
                        exit_price=round(exit_fill_p, 2),
                        quantity=pos_qty,
                        notional_entry=round(pos_entry_price * pos_qty, 2),
                        notional_exit=round(exit_fill_p * pos_qty, 2),
                        fee_paid=round(total_fee, 3),
                        slippage_paid=round(total_slip, 3),
                        gross_pnl=round(gross_pnl, 2),
                        net_pnl=round(net_pnl, 2),
                        pnl_percent=round((net_pnl / (pos_entry_price * pos_qty)) * 100.0, 3),
                        r_multiple=round(r_mult, 3),
                        mfe=round(mfe, 2),
                        mae=round(mae, 2),
                        exit_reason=exit_reason,
                        holding_period_minutes=float(pos_bars_held),
                    )
                    ledger.record_trade(trade)
                    current_equity += net_pnl
                    in_position = False

            # ----------------------------------------------------
            # 3. Check for New Signal at Close of this bar (t)
            # ----------------------------------------------------
            close_time = int(bar.get("close_time", 0)) if "close_time" in bar else None
            if not in_position:
                if curr_time in signals_by_ts:
                    pending_signal = signals_by_ts[curr_time]
                elif close_time is not None and close_time in signals_by_ts:
                    pending_signal = signals_by_ts[close_time]

        # Calculate final metrics and equity curve
        metrics = MetricCalculator.compute_metrics(
            trades=ledger.trades,
            initial_capital=self.initial_capital,
            total_bars=len(df),
            intrabar_ambiguity_count=intrabar_ambiguity_count,
        )
        equity_curve = ledger.get_equity_curve(initial_capital=self.initial_capital)

        return BacktestResult(ledger=ledger, metrics=metrics, equity_curve=equity_curve)
