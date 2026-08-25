"""Accelerated Historical Market Replay Engine.

Replays historical 1m kline data through the live event pipeline at accelerated speed
(e.g., 1 day in 30 seconds) for end-to-end operational verification before connecting to live sockets.
"""

import time
from typing import Optional, Callable, Dict, Any, List
import polars as pl
from pydantic import BaseModel, Field

from quant_platform.live.state_engine import LiveStateEngine
from quant_platform.observability.logger import logger


class ReplayResult(BaseModel):
    """Execution summary of a market replay session."""
    symbol: str
    total_bars_replayed: int
    duration_seconds: float
    simulated_days: float
    effective_speed_multiplier: float
    final_price: float
    total_recalculated_states: int


class MarketReplayEngine:
    """Streams historical klines through the live engine to simulate live market flow."""

    def __init__(
        self,
        state_engine: Optional[LiveStateEngine] = None,
        speed_multiplier: float = 0.0, # 0.0 means instant (no sleep)
    ):
        self.state_engine = state_engine or LiveStateEngine()
        self.speed_multiplier = speed_multiplier

    def replay(
        self,
        df_1m: pl.DataFrame,
        on_bar_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> ReplayResult:
        """Run accelerated replay of historical dataframe."""
        total_bars = len(df_1m)
        if total_bars == 0:
            raise ValueError("Cannot replay empty DataFrame.")

        logger.info(f"Starting Market Replay of {total_bars} bars (Speed: {'Instant' if self.speed_multiplier == 0 else f'{self.speed_multiplier}x'})...")
        t_start = time.time()
        recalc_count = 0

        # Determine sleep interval per candle if speed > 0
        sleep_sec = (60.0 / self.speed_multiplier) if self.speed_multiplier > 0 else 0.0

        for row in df_1m.iter_rows(named=True):
            triggered = self.state_engine.on_1m_candle(
                open_time=row["open_time"],
                open_price=row["open"],
                high_price=row["high"],
                low_price=row["low"],
                close_price=row["close"],
                volume=row["volume"],
                close_time=row["close_time"],
                is_closed=True,
                quote_volume=row.get("quote_asset_volume", 0.0),
                trades=row.get("number_of_trades", 0),
            )

            if triggered:
                recalc_count += 1
                if on_bar_callback:
                    snap = self.state_engine.get_latest_snapshot()
                    on_bar_callback(snap)

            if sleep_sec > 0:
                time.sleep(sleep_sec)

        elapsed = time.time() - t_start
        sim_days = total_bars / (60.0 * 24.0)
        eff_speed = (total_bars * 60.0) / max(0.001, elapsed)

        logger.info(f"Replay Complete: {total_bars} bars ({sim_days:.2f} simulated days) in {elapsed:.2f}s (Effective: {eff_speed:.0f}x live speed).")

        return ReplayResult(
            symbol=self.state_engine.symbol,
            total_bars_replayed=total_bars,
            duration_seconds=elapsed,
            simulated_days=sim_days,
            effective_speed_multiplier=eff_speed,
            final_price=self.state_engine.current_live_price,
            total_recalculated_states=recalc_count,
        )
