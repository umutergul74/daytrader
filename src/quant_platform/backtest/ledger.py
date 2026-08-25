"""Trade ledger for recording and aggregating trade executions."""

from typing import List, Dict, Any, Optional
import polars as pl
from pydantic import BaseModel, Field

from quant_platform.domain.trade import TradeRecord


class TradeLedger:
    """Manages collection of executed trade records and exports."""

    def __init__(self):
        self.trades: List[TradeRecord] = []

    def record_trade(self, trade: TradeRecord) -> None:
        self.trades.append(trade)

    @property
    def trade_count(self) -> int:
        return len(self.trades)

    def to_dataframe(self) -> pl.DataFrame:
        """Convert recorded trades into a typed Polars DataFrame."""
        if not self.trades:
            return pl.DataFrame()
        dicts = [t.model_dump() for t in self.trades]
        return pl.DataFrame(dicts)

    def get_equity_curve(self, initial_capital: float = 10000.0) -> pl.DataFrame:
        """Generate cumulative equity curve series."""
        if not self.trades:
            return pl.DataFrame({"trade_index": [0], "equity": [initial_capital], "net_pnl": [0.0]})

        pnl_series = [t.net_pnl for t in self.trades]
        equity = initial_capital
        equity_values = [initial_capital]
        timestamps = [self.trades[0].entry_time]

        for t in self.trades:
            equity += t.net_pnl
            equity_values.append(equity)
            timestamps.append(t.exit_time)

        return pl.DataFrame({
            "trade_index": list(range(len(equity_values))),
            "timestamp": timestamps,
            "equity": equity_values,
        })
