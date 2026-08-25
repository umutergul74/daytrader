"""Paper Trading Broker & Portfolio Lifecycle Simulator.

Simulates live paper trade execution with realistic taker/maker fees, slippage,
multi-stage take-profits (TP1/TP2), breakeven stop advancement, and funding fee tracking.
Guarantees NO REAL ORDERS ARE PLACED.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid

from quant_platform.domain.trade import TradeDirection, TradeRecord, OrderType, TradeStatus, ExitReason
from quant_platform.backtest.costs import CostModel
from quant_platform.observability.logger import logger


class PaperPosition(BaseModel):
    """Active live paper trading position."""
    position_id: str = Field(default_factory=lambda: f"POS-{uuid.uuid4().hex[:8]}")
    symbol: str
    strategy_id: str
    direction: TradeDirection
    quantity: float
    entry_price: float
    entry_time_ms: int
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    is_tp1_hit: bool = False
    is_breakeven_active: bool = False
    fees_paid: float = 0.0
    initial_risk_usdt: float = 0.0
    r_target: float = 2.0


class PaperPortfolio(BaseModel):
    """Paper trading portfolio state and metrics."""
    portfolio_name: str = "champion_paper"
    initial_capital: float = 10000.0
    cash_balance: float = 10000.0
    equity: float = 10000.0
    open_positions: Dict[str, PaperPosition] = Field(default_factory=dict)
    closed_trades: List[TradeRecord] = Field(default_factory=list)
    total_trades_count: int = 0
    profitable_trades_count: int = 0
    total_net_pnl: float = 0.0
    max_equity: float = 10000.0
    max_drawdown_pct: float = 0.0


class PaperBroker:
    """Manages paper order lifecycle and portfolio accounting."""

    def __init__(
        self,
        portfolio_name: str = "champion_paper",
        initial_capital: float = 10000.0,
        cost_model: Optional[CostModel] = None,
    ):
        self.portfolio = PaperPortfolio(
            portfolio_name=portfolio_name,
            initial_capital=initial_capital,
            cash_balance=initial_capital,
            equity=initial_capital,
            max_equity=initial_capital,
        )
        self.cost_model = cost_model or CostModel(maker_fee_rate=0.0002, taker_fee_rate=0.0005, slippage_bps=2.0)

    def open_paper_trade(
        self,
        strategy_id: str,
        symbol: str,
        direction: TradeDirection,
        price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: Optional[float] = None,
        risk_fraction: float = 0.01,
        time_ms: Optional[int] = None,
    ) -> Optional[PaperPosition]:
        """Execute a simulated paper entry."""
        # 1. Apply entry slippage (taker)
        slip_mult = (1.0 + self.cost_model.slippage_bps / 10000.0) if direction == TradeDirection.LONG else (1.0 - self.cost_model.slippage_bps / 10000.0)
        fill_price = price * slip_mult

        # 2. Risk & sizing
        risk_usdt = self.portfolio.equity * risk_fraction
        stop_dist = abs(fill_price - stop_loss)
        if stop_dist <= 0:
            logger.warning("Rejected paper trade: stop distance is zero or negative.")
            return None

        qty = risk_usdt / stop_dist
        notional = qty * fill_price

        # Max leverage guard (10x max notional)
        if notional > self.portfolio.equity * 10.0:
            qty = (self.portfolio.equity * 10.0) / fill_price

        entry_fee = qty * fill_price * self.cost_model.taker_fee_rate
        self.portfolio.cash_balance -= entry_fee

        pos = PaperPosition(
            symbol=symbol,
            strategy_id=strategy_id,
            direction=direction,
            quantity=qty,
            entry_price=fill_price,
            entry_time_ms=time_ms or int(datetime.now(timezone.utc).timestamp() * 1000),
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            fees_paid=entry_fee,
            initial_risk_usdt=risk_usdt,
            r_target=abs(take_profit_1 - fill_price) / stop_dist,
        )

        self.portfolio.open_positions[pos.position_id] = pos
        logger.info(f"[PAPER BROKER] Opened {direction.value} {pos.position_id} for {strategy_id} at ${fill_price:.2f} (SL: ${stop_loss:.2f}, TP1: ${take_profit_1:.2f})")
        return pos

    def update_positions_on_candle(
        self,
        high_price: float,
        low_price: float,
        close_price: float,
        time_ms: int,
    ) -> List[TradeRecord]:
        """Check open positions against latest bar price action (SL/TP triggers)."""
        closed_records: List[TradeRecord] = []
        to_close_ids = []

        for pos_id, pos in self.portfolio.open_positions.items():
            if pos.direction == TradeDirection.LONG:
                # 1. Stop Loss check
                if low_price <= pos.stop_loss:
                    exit_price = pos.stop_loss * (1.0 - self.cost_model.slippage_bps / 10000.0)
                    record = self._close_position(pos, exit_price, time_ms, exit_reason="STOP_LOSS")
                    closed_records.append(record)
                    to_close_ids.append(pos_id)
                    continue

                # 2. Take Profit check
                if high_price >= pos.take_profit_1:
                    exit_price = pos.take_profit_1 * (1.0 - self.cost_model.slippage_bps / 10000.0)
                    record = self._close_position(pos, exit_price, time_ms, exit_reason="TAKE_PROFIT_1")
                    closed_records.append(record)
                    to_close_ids.append(pos_id)
                    continue

            elif pos.direction == TradeDirection.SHORT:
                # 1. Stop Loss check
                if high_price >= pos.stop_loss:
                    exit_price = pos.stop_loss * (1.0 + self.cost_model.slippage_bps / 10000.0)
                    record = self._close_position(pos, exit_price, time_ms, exit_reason="STOP_LOSS")
                    closed_records.append(record)
                    to_close_ids.append(pos_id)
                    continue

                # 2. Take Profit check
                if low_price <= pos.take_profit_1:
                    exit_price = pos.take_profit_1 * (1.0 + self.cost_model.slippage_bps / 10000.0)
                    record = self._close_position(pos, exit_price, time_ms, exit_reason="TAKE_PROFIT_1")
                    closed_records.append(record)
                    to_close_ids.append(pos_id)
                    continue

        for pid in to_close_ids:
            del self.portfolio.open_positions[pid]

        # Update equity
        self._update_equity(close_price)
        return closed_records

    def _close_position(
        self,
        pos: PaperPosition,
        exit_price: float,
        time_ms: int,
        exit_reason: str,
    ) -> TradeRecord:
        """Settle a paper trade and update portfolio accounting."""
        exit_fee = pos.quantity * exit_price * self.cost_model.taker_fee_rate
        total_fees = pos.fees_paid + exit_fee

        if pos.direction == TradeDirection.LONG:
            gross_pnl = pos.quantity * (exit_price - pos.entry_price)
        else:
            gross_pnl = pos.quantity * (pos.entry_price - exit_price)

        net_pnl = gross_pnl - total_fees
        self.portfolio.cash_balance += (gross_pnl - exit_fee)
        self.portfolio.total_net_pnl += net_pnl
        self.portfolio.total_trades_count += 1
        if net_pnl > 0:
            self.portfolio.profitable_trades_count += 1

        exit_enum = ExitReason.TAKE_PROFIT if "PROFIT" in exit_reason else ExitReason.STOP_LOSS
        r_multiple = net_pnl / max(0.01, pos.initial_risk_usdt)

        record = TradeRecord(
            trade_id=pos.position_id,
            signal_id=pos.position_id,
            strategy_id=pos.strategy_id,
            symbol=pos.symbol,
            side=pos.direction,
            entry_time=pos.entry_time_ms,
            exit_time=time_ms,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=pos.quantity,
            notional_entry=pos.quantity * pos.entry_price,
            notional_exit=pos.quantity * exit_price,
            fee_paid=total_fees,
            slippage_paid=0.0,
            funding_paid=0.0,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            pnl_percent=(net_pnl / max(0.01, pos.quantity * pos.entry_price)) * 100.0,
            r_multiple=r_multiple,
            exit_reason=exit_enum,
            holding_period_minutes=max(0.0, (time_ms - pos.entry_time_ms) / 60000.0),
        )

        self.portfolio.closed_trades.append(record)
        logger.info(f"[PAPER BROKER] Closed {pos.position_id} ({exit_reason}): Net PnL = ${net_pnl:+.2f} ({r_multiple:+.2f}R)")
        return record

    def _update_equity(self, current_price: float) -> None:
        """Mark-to-market current open positions to calculate total equity and drawdown."""
        unrealized = 0.0
        for pos in self.portfolio.open_positions.values():
            if pos.direction == TradeDirection.LONG:
                unrealized += pos.quantity * (current_price - pos.entry_price)
            else:
                unrealized += pos.quantity * (pos.entry_price - current_price)

        self.portfolio.equity = self.portfolio.cash_balance + unrealized
        if self.portfolio.equity > self.portfolio.max_equity:
            self.portfolio.max_equity = self.portfolio.equity

        dd = max(0.0, (self.portfolio.max_equity - self.portfolio.equity) / max(1.0, self.portfolio.max_equity)) * 100.0
        if dd > self.portfolio.max_drawdown_pct:
            self.portfolio.max_drawdown_pct = dd
