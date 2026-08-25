"""Random Direction Sanity Baseline Strategy."""

import random
from typing import List, Dict, Any
import polars as pl

from quant_platform.domain.signal import (
    SignalCandidate,
    SignalDirection,
    SignalType,
    StopCandidate,
    TargetCandidate,
)
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class RandomSanityBaseline(BaseStrategy):
    """Deterministic pseudo-random trading baseline to establish non-informative alpha floor."""

    def __init__(
        self,
        seed: int = 42,
        trade_probability_per_bar: float = 0.05,
        atr_period: int = 14,
        atr_multiplier_stop: float = 2.0,
        risk_reward_ratio: float = 2.0,
    ):
        self.seed = seed
        self.trade_probability_per_bar = trade_probability_per_bar
        self.atr_period = atr_period
        self.atr_multiplier_stop = atr_multiplier_stop
        self.risk_reward_ratio = risk_reward_ratio

        metadata = StrategyMetadata(
            strategy_id="baseline:random_sanity:v1",
            version="v1",
            hypothesis="Sanity benchmark providing expected performance under zero predictive skill.",
            required_features=["technical:atr:v1"],
            parameters={
                "seed": seed,
                "trade_probability_per_bar": trade_probability_per_bar,
                "atr_period": atr_period,
                "atr_multiplier_stop": atr_multiplier_stop,
                "risk_reward_ratio": risk_reward_ratio,
            },
        )
        super().__init__(metadata)

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        if len(df) < self.atr_period + 5:
            return []

        rng = random.Random(self.seed)
        atr_col = f"atr_{self.atr_period}"
        df_calc = compute_atr(df, period=self.atr_period, output_col=atr_col)

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        for i, row in enumerate(rows):
            if i < self.atr_period + 2:
                continue

            if rng.random() > self.trade_probability_per_bar:
                continue

            curr_close = row["close"]
            curr_atr = row[atr_col]
            timestamp_ms = int(row["open_time"])

            if curr_atr is None or curr_atr <= 0:
                continue

            direction = SignalDirection.LONG if rng.random() > 0.5 else SignalDirection.SHORT
            stop_dist = curr_atr * self.atr_multiplier_stop
            tp_dist = stop_dist * self.risk_reward_ratio

            stop_price = curr_close - stop_dist if direction == SignalDirection.LONG else curr_close + stop_dist
            tp_price = curr_close + tp_dist if direction == SignalDirection.LONG else curr_close - tp_dist

            signals.append(SignalCandidate(
                signal_id=f"SIG-RND-{timestamp_ms}-{direction.value}",
                strategy_id=self.metadata.strategy_id,
                strategy_version=self.metadata.version,
                timestamp=timestamp_ms,
                symbol="ETHUSDT",
                direction=direction,
                entry_type=SignalType.MARKET,
                entry_price=curr_close,
                stop_candidate=StopCandidate(
                    name="ATR_STOP",
                    price=round(stop_price, 2),
                    risk_distance=round(stop_dist, 2),
                ),
                target_candidates=[
                    TargetCandidate(
                        name="TP1",
                        price=round(tp_price, 2),
                        reward_r=self.risk_reward_ratio,
                    )
                ],
                calculated_rr=self.risk_reward_ratio,
                evidence=["Deterministic seeded pseudo-random signal"],
            ))

        return signals
