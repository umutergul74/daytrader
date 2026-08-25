"""Live Causal State Engine and Rolling Candle Buffer.

Maintains multi-timeframe rolling buffers (1m, 5m, 15m, 1h, 4h) and triggers
causal feature recalculation ONLY upon finalized candle close.
"""

from typing import Dict, List, Optional, Any, Callable
from collections import deque
from datetime import datetime, timezone
import polars as pl
import numpy as np

from quant_platform.features.indicators.trend import compute_ema
from quant_platform.features.indicators.momentum import compute_rsi
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.features.structure.market_structure import MarketStructureEngine
from quant_platform.features.smc.fvg import FvgEngine
from quant_platform.features.smc.liquidity import LiquidityEngine
from quant_platform.regimes.engine import MarketRegimeEngine
from quant_platform.data.timeframes.resampler import CausalResampler
from quant_platform.observability.logger import logger


class LiveStateEngine:
    """Maintains causal streaming bar buffers and incrementally computes features."""

    def __init__(
        self,
        symbol: str = "ETHUSDT",
        max_1m_bars: int = 2000,
        timeframes: Optional[List[str]] = None,
    ):
        self.symbol = symbol
        self.max_1m_bars = max_1m_bars
        self.timeframes = timeframes or ["1m", "5m", "15m", "1h"]

        # Raw 1m kline buffer
        self._raw_1m_bars: deque = deque(maxlen=max_1m_bars)
        self.last_finalized_1m_ts: int = 0
        self.current_live_price: float = 0.0
        self.latest_data_lag_ms: int = 0

        # Cached computed Polars DataFrames per timeframe
        self.computed_dfs: Dict[str, pl.DataFrame] = {}

    def on_1m_candle(
        self,
        open_time: int,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: float,
        close_time: int,
        is_closed: bool = True,
        quote_volume: float = 0.0,
        trades: int = 0,
    ) -> bool:
        """Ingest a 1m candle event. Returns True if a finalized candle triggered recalculation."""
        self.current_live_price = close_price
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        self.latest_data_lag_ms = max(0, now_ms - close_time)

        if not is_closed:
            return False

        # Avoid duplicate ingestion
        if self._raw_1m_bars and self._raw_1m_bars[-1]["open_time"] == open_time:
            self._raw_1m_bars[-1] = {
                "open_time": open_time,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "close_time": close_time,
                "quote_asset_volume": quote_volume or (volume * close_price),
                "number_of_trades": trades or int(volume),
                "taker_buy_base_asset_volume": volume * 0.5,
                "taker_buy_quote_asset_volume": (volume * close_price) * 0.5,
                "available_at_ms": close_time + 1,
            }
        else:
            self._raw_1m_bars.append({
                "open_time": open_time,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "close_time": close_time,
                "quote_asset_volume": quote_volume or (volume * close_price),
                "number_of_trades": trades or int(volume),
                "taker_buy_base_asset_volume": volume * 0.5,
                "taker_buy_quote_asset_volume": (volume * close_price) * 0.5,
                "available_at_ms": close_time + 1,
            })

        self.last_finalized_1m_ts = open_time

        # Recompute features across timeframes
        self._recompute_state(close_time=close_time)
        return True

    TF_MS = {
        "1m": 60_000,
        "5m": 300_000,
        "15m": 900_000,
        "1h": 3_600_000,
        "4h": 14_400_000,
        "1d": 86_400_000,
    }

    def _recompute_state(self, close_time: int) -> None:
        """Causally recomputes multi-timeframe aggregations and indicators on bar closure boundaries."""
        if len(self._raw_1m_bars) < 10:
            return

        df_1m = pl.DataFrame(list(self._raw_1m_bars))
        self.computed_dfs["1m"] = df_1m

        for tf in self.timeframes:
            if tf == "1m":
                continue

            tf_ms = self.TF_MS.get(tf, 900_000)
            is_boundary = ((close_time + 1) % tf_ms == 0)

            # Only resample and recalculate if higher timeframe bar just closed or dataframe missing
            if is_boundary or (tf not in self.computed_dfs):
                df_tf = CausalResampler.resample(df_1m, target_timeframe=tf)

                if len(df_tf) >= 15:
                    # Add core indicators
                    df_tf = compute_ema(df_tf, period=10, output_col="ema_10")
                    df_tf = compute_ema(df_tf, period=30, output_col="ema_30")
                    df_tf = compute_rsi(df_tf, period=14, output_col="rsi_14")
                    df_tf = compute_atr(df_tf, period=14, output_col="atr_14")

                    # Add Market Structure & SMC
                    df_tf = MarketStructureEngine.compute_market_structure(df_tf, left_bars=3, right_bars=3)
                    df_tf, _ = FvgEngine.detect_and_track_fvgs(df_tf)
                    df_tf, _ = LiquidityEngine.detect_liquidity_sweeps(df_tf, left_bars=3, right_bars=3)
                    df_tf = MarketRegimeEngine.classify_regimes(df_tf)

                self.computed_dfs[tf] = df_tf

    def get_latest_snapshot(self) -> Dict[str, Any]:
        """Returns structured current market intelligence snapshot."""
        df_15m = self.computed_dfs.get("15m")
        df_1h = self.computed_dfs.get("1h")

        regime_str = "UNKNOWN"
        structure_15m = "NEUTRAL"
        structure_1h = "NEUTRAL"
        active_fvg = 0
        sweep_active = False

        if df_15m is not None and len(df_15m) > 0:
            last_row = df_15m.tail(1).to_dicts()[0]
            regime_str = last_row.get("regime_tag", "UNKNOWN")
            trend_val = last_row.get("structural_trend", 0)
            structure_15m = "BULLISH" if trend_val == 1 else ("BEARISH" if trend_val == -1 else "NEUTRAL")
            active_fvg = last_row.get("active_bullish_fvg_count", 0) + last_row.get("active_bearish_fvg_count", 0)
            sweep_active = bool(last_row.get("is_sellside_sweep", False) or last_row.get("is_buyside_sweep", False))

        if df_1h is not None and len(df_1h) > 0:
            trend_1h = df_1h.tail(1).to_dicts()[0].get("structural_trend", 0)
            structure_1h = "BULLISH" if trend_1h == 1 else ("BEARISH" if trend_1h == -1 else "NEUTRAL")

        return {
            "symbol": self.symbol,
            "live_price": self.current_live_price,
            "last_finalized_1m": self.last_finalized_1m_ts,
            "data_lag_ms": self.latest_data_lag_ms,
            "regime": regime_str,
            "structure_1h": structure_1h,
            "structure_15m": structure_15m,
            "active_fvgs": active_fvg,
            "liquidity_sweep_active": sweep_active,
        }
