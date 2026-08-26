"""Unified Microstructure and Kline Event Replay Engine.

Interleaves heterogeneous event streams (Klines, AggTrades, Open Interest, Liquidations)
in strict monotonic chronological order for causal high-fidelity simulation.
"""

import heapq
from typing import Dict, List, Optional, Any, Callable, Generator, Tuple
import polars as pl
from pydantic import BaseModel

from quant_platform.domain.events import MicrostructureEventType
from quant_platform.observability.logger import logger


class UnifiedEvent(BaseModel):
    """Wrapper container for heterogeneous event streams."""
    event_type: MicrostructureEventType
    event_time_ms: int
    data: Dict[str, Any]

    def __lt__(self, other: "UnifiedEvent") -> bool:
        return self.event_time_ms < other.event_time_ms


class UnifiedEventReplayEngine:
    """Streams interleaved multi-source market events in exact event-time order."""

    @staticmethod
    def create_interleaved_stream(
        df_klines: Optional[pl.DataFrame] = None,
        df_agg_trades: Optional[pl.DataFrame] = None,
        df_open_interest: Optional[pl.DataFrame] = None,
        df_liquidations: Optional[pl.DataFrame] = None,
    ) -> Generator[UnifiedEvent, None, None]:
        """Yields UnifiedEvents sorted chronologically using a min-heap."""
        # Create generator streams
        streams = []

        if df_klines is not None and not df_klines.is_empty():
            def kline_gen():
                for row in df_klines.iter_rows(named=True):
                    yield UnifiedEvent(
                        event_type=MicrostructureEventType.KLINE,
                        event_time_ms=row["close_time"],
                        data=row,
                    )
            streams.append(kline_gen())

        if df_agg_trades is not None and not df_agg_trades.is_empty():
            def trade_gen():
                for row in df_agg_trades.iter_rows(named=True):
                    yield UnifiedEvent(
                        event_type=MicrostructureEventType.AGG_TRADE,
                        event_time_ms=row["event_time_ms"],
                        data=row,
                    )
            streams.append(trade_gen())

        if df_open_interest is not None and not df_open_interest.is_empty():
            def oi_gen():
                for row in df_open_interest.iter_rows(named=True):
                    yield UnifiedEvent(
                        event_type=MicrostructureEventType.OPEN_INTEREST,
                        event_time_ms=row["event_time_ms"],
                        data=row,
                    )
            streams.append(oi_gen())

        if df_liquidations is not None and not df_liquidations.is_empty():
            def liq_gen():
                for row in df_liquidations.iter_rows(named=True):
                    yield UnifiedEvent(
                        event_type=MicrostructureEventType.LIQUIDATION,
                        event_time_ms=row["event_time_ms"],
                        data=row,
                    )
            streams.append(liq_gen())

        # Interleave using heapq.merge
        for event in heapq.merge(*streams):
            yield event
