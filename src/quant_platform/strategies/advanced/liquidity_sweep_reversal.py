"""Liquidity Sweep Reversal Strategy."""

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
from quant_platform.features.smc.liquidity import LiquidityEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class LiquiditySweepReversalStrategy(BaseStrategy):
    """Trades mean reversion upon liquidity pool sweeps and structural reclaims."""

    def __init__(
        self,
        left_bars: int = 5,
        right_bars: int = 5,
        atr_period: int = 14,
        risk_reward_ratio: float = 2.0,
    ):
        self.left_bars = left_bars
        self.right_bars = right_bars
        self.atr_period = atr_period
        self.risk_reward_ratio = risk_reward_ratio

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="smc:liquidity_sweep_reversal",
            version="v1",
            family="smc",
            hypothesis="When resting liquidity is swept and price reclaims inside the level, trapped participants create sharp reversal flow.",
            parameters={
                "left_bars": self.left_bars,
                "right_bars": self.right_bars,
                "atr_period": self.atr_period,
                "risk_reward_ratio": self.risk_reward_ratio,
            },
            required_features=["smc:liquidity_sweep", "volatility:atr"],
        )

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        df_calc, sweeps = LiquidityEngine.detect_liquidity_sweeps(
            df,
            left_bars=self.left_bars,
            right_bars=self.right_bars,
            atr_period=self.atr_period,
        )
        atr_col = f"atr_{self.atr_period}"
        df_calc = compute_atr(df_calc, period=self.atr_period, output_col=atr_col)

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        for row in rows:
            is_sell_rec = row["is_sellside_reclaim"]
            is_buy_rec = row["is_buyside_reclaim"]
            close = row["close"]
            low = row["low"]
            high = row["high"]
            atr_val = row[atr_col]

            if atr_val is None:
                continue

            # Bullish Reversal on Sell-side Sweep & Reclaim
            if is_sell_rec:
                stop_price = low - (0.2 * atr_val)
                risk_dist = close - stop_price
                if risk_dist > 0:
                    tp_price = close + (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-SWP-BULL-{row['open_time']}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=row["close_time"],
                        direction=SignalDirection.LONG,
                        entry_price=close,
                        stop_candidate=StopCandidate(name="SWEEP_LOW_SL", price=stop_price, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                    ))

            # Bearish Reversal on Buy-side Sweep & Reclaim
            elif is_buy_rec:
                stop_price = high + (0.2 * atr_val)
                risk_dist = stop_price - close
                if risk_dist > 0:
                    tp_price = close - (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-SWP-BEAR-{row['open_time']}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=row["close_time"],
                        direction=SignalDirection.SHORT,
                        entry_price=close,
                        stop_candidate=StopCandidate(name="SWEEP_HIGH_SL", price=stop_price, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                    ))

        return signals
