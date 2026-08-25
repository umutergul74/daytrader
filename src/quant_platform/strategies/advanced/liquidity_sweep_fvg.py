"""Liquidity Sweep + Fair Value Gap Retest Strategy."""

from typing import List, Optional
import polars as pl

from quant_platform.domain.signal import (
    SignalCandidate,
    SignalDirection,
    SignalType,
    StopCandidate,
    TargetCandidate,
)
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.features.smc.fvg import FvgEngine
from quant_platform.features.smc.liquidity import LiquidityEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class LiquiditySweepFVGStrategy(BaseStrategy):
    """Trades FVG mitigations formed following a liquidity sweep and displacement."""

    def __init__(
        self,
        left_bars: int = 5,
        right_bars: int = 5,
        atr_period: int = 14,
        min_gap_atr_ratio: float = 0.2,
        risk_reward_ratio: float = 2.0,
    ):
        self.left_bars = left_bars
        self.right_bars = right_bars
        self.atr_period = atr_period
        self.min_gap_atr_ratio = min_gap_atr_ratio
        self.risk_reward_ratio = risk_reward_ratio

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="smc:liquidity_sweep_fvg",
            version="v1",
            family="smc",
            hypothesis="Liquidity sweep followed by displacement and FVG retest yields higher probability reversal entries than raw sweeps alone.",
            parameters={
                "left_bars": self.left_bars,
                "right_bars": self.right_bars,
                "atr_period": self.atr_period,
                "min_gap_atr_ratio": self.min_gap_atr_ratio,
                "risk_reward_ratio": self.risk_reward_ratio,
            },
            required_features=["smc:liquidity_sweep", "smc:fvg_three_candle", "volatility:atr"],
        )

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        df_swp, _ = LiquidityEngine.detect_liquidity_sweeps(
            df,
            left_bars=self.left_bars,
            right_bars=self.right_bars,
            atr_period=self.atr_period,
        )
        df_calc, _ = FvgEngine.detect_and_track_fvgs(
            df_swp,
            atr_period=self.atr_period,
            min_gap_atr_ratio=self.min_gap_atr_ratio,
        )
        atr_col = f"atr_{self.atr_period}"
        df_calc = compute_atr(df_calc, period=self.atr_period, output_col=atr_col)

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        recent_bull_sweep = 0
        recent_bear_sweep = 0

        for row in rows:
            is_sell_rec = row["is_sellside_reclaim"]
            is_buy_rec = row["is_buyside_reclaim"]
            is_inside_bull = row["is_inside_bullish_fvg"]
            is_inside_bear = row["is_inside_bearish_fvg"]
            close = row["close"]
            low = row["low"]
            high = row["high"]
            atr_val = row[atr_col]

            if is_sell_rec:
                recent_bull_sweep = 10 # valid for 10 bars
            else:
                recent_bull_sweep = max(0, recent_bull_sweep - 1)

            if is_buy_rec:
                recent_bear_sweep = 10
            else:
                recent_bear_sweep = max(0, recent_bear_sweep - 1)

            if atr_val is None:
                continue

            # Bullish: Recent sell-side sweep + price enters active Bullish FVG
            if recent_bull_sweep > 0 and is_inside_bull:
                stop_price = low - (0.5 * atr_val)
                risk_dist = close - stop_price
                if risk_dist > 0:
                    tp_price = close + (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-SWP-FVG-BULL-{row['open_time']}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=row["close_time"],
                        direction=SignalDirection.LONG,
                        entry_price=close,
                        stop_candidate=StopCandidate(name="FVG_LOW_SL", price=stop_price, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                    ))
                    recent_bull_sweep = 0 # consume trigger

            # Bearish: Recent buy-side sweep + price enters active Bearish FVG
            elif recent_bear_sweep > 0 and is_inside_bear:
                stop_price = high + (0.5 * atr_val)
                risk_dist = stop_price - close
                if risk_dist > 0:
                    tp_price = close - (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-SWP-FVG-BEAR-{row['open_time']}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=row["close_time"],
                        direction=SignalDirection.SHORT,
                        entry_price=close,
                        stop_candidate=StopCandidate(name="FVG_HIGH_SL", price=stop_price, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                    ))
                    recent_bear_sweep = 0

        return signals
