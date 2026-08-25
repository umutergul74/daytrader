"""Fair Value Gap Trend Continuation Strategy."""

from typing import List, Optional
import polars as pl

from quant_platform.domain.signal import (
    SignalCandidate,
    SignalDirection,
    SignalType,
    StopCandidate,
    TargetCandidate,
)
from quant_platform.features.indicators.trend import compute_ema, compute_adx
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.features.smc.fvg import FvgEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class FvgTrendContinuationStrategy(BaseStrategy):
    """Trades FVG pullbacks in the direction of strong trend."""

    def __init__(
        self,
        fast_ema: int = 20,
        slow_ema: int = 50,
        atr_period: int = 14,
        adx_min: float = 20.0,
        risk_reward_ratio: float = 2.0,
    ):
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.atr_period = atr_period
        self.adx_min = adx_min
        self.risk_reward_ratio = risk_reward_ratio

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="smc:fvg_trend_continuation",
            version="v1",
            family="smc",
            hypothesis="Retesting newly created FVGs within strong trending regimes offers high-expectancy trend re-entries.",
            parameters={
                "fast_ema": self.fast_ema,
                "slow_ema": self.slow_ema,
                "atr_period": self.atr_period,
                "adx_min": self.adx_min,
                "risk_reward_ratio": self.risk_reward_ratio,
            },
            required_features=["smc:fvg_three_candle", "trend:ema", "trend:adx", "volatility:atr"],
        )

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        df_calc = compute_ema(df, period=self.fast_ema, output_col=f"ema_{self.fast_ema}")
        df_calc = compute_ema(df_calc, period=self.slow_ema, output_col=f"ema_{self.slow_ema}")
        df_calc = compute_adx(df_calc, period=14)
        df_calc = compute_atr(df_calc, period=self.atr_period, output_col=f"atr_{self.atr_period}")
        df_calc, _ = FvgEngine.detect_and_track_fvgs(df_calc, atr_period=self.atr_period)

        fast_col = f"ema_{self.fast_ema}"
        slow_col = f"ema_{self.slow_ema}"
        atr_col = f"atr_{self.atr_period}"

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        for row in rows:
            fast_val = row[fast_col]
            slow_val = row[slow_col]
            adx_val = row["adx_14"]
            atr_val = row[atr_col]
            is_inside_bull = row["is_inside_bullish_fvg"]
            is_inside_bear = row["is_inside_bearish_fvg"]
            close = row["close"]
            low = row["low"]
            high = row["high"]

            if fast_val is None or slow_val is None or adx_val is None or atr_val is None:
                continue

            # Bullish Trend + FVG Retest
            if fast_val > slow_val and adx_val >= self.adx_min and is_inside_bull:
                stop_price = low - (1.0 * atr_val)
                risk_dist = close - stop_price
                if risk_dist > 0:
                    tp_price = close + (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-FVG-CONT-BULL-{row['open_time']}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=row["close_time"],
                        direction=SignalDirection.LONG,
                        entry_price=close,
                        stop_candidate=StopCandidate(name="FVG_PULLBACK_SL", price=stop_price, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                    ))

            # Bearish Trend + FVG Retest
            elif fast_val < slow_val and adx_val >= self.adx_min and is_inside_bear:
                stop_price = high + (1.0 * atr_val)
                risk_dist = stop_price - close
                if risk_dist > 0:
                    tp_price = close - (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-FVG-CONT-BEAR-{row['open_time']}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=row["close_time"],
                        direction=SignalDirection.SHORT,
                        entry_price=close,
                        stop_candidate=StopCandidate(name="FVG_PULLBACK_SL", price=stop_price, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                    ))

        return signals
