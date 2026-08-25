"""Channel Breakout Baseline Strategy."""

from typing import List, Dict, Any, Optional
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


class BreakoutSanityStrategy(BaseStrategy):
    """Channel breakout baseline (Donchian-style high/low breakout)."""

    def __init__(
        self,
        lookback_period: int = 20,
        atr_period: int = 14,
        atr_multiplier_stop: float = 2.0,
        risk_reward_ratio: float = 2.0,
    ):
        self.lookback_period = lookback_period
        self.atr_period = atr_period
        self.atr_multiplier_stop = atr_multiplier_stop
        self.risk_reward_ratio = risk_reward_ratio

        metadata = StrategyMetadata(
            strategy_id="baseline:breakout:v1",
            version="v1",
            hypothesis="Price breaking above the N-bar high continues with momentum in the breakout direction.",
            required_features=["technical:atr:v1"],
            parameters={
                "lookback_period": lookback_period,
                "atr_period": atr_period,
                "atr_multiplier_stop": atr_multiplier_stop,
                "risk_reward_ratio": risk_reward_ratio,
            },
        )
        super().__init__(metadata)

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        if len(df) < max(self.lookback_period, self.atr_period) + 5:
            return []

        atr_col = f"atr_{self.atr_period}"
        df_calc = compute_atr(df, period=self.atr_period, output_col=atr_col)

        # Compute rolling high and low shifted by 1 (to be strictly causal)
        df_calc = df_calc.with_columns([
            pl.col("high").shift(1).rolling_max(window_size=self.lookback_period).alias("_ch_high"),
            pl.col("low").shift(1).rolling_min(window_size=self.lookback_period).alias("_ch_low"),
        ])

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        for i, row in enumerate(rows):
            if i < self.lookback_period + 2:
                continue

            ch_high = row["_ch_high"]
            ch_low = row["_ch_low"]
            curr_close = row["close"]
            curr_atr = row[atr_col]
            timestamp_ms = int(row["open_time"])

            if ch_high is None or ch_low is None or curr_atr is None or curr_atr <= 0:
                continue

            # Breakout Long
            if curr_close > ch_high:
                stop_dist = curr_atr * self.atr_multiplier_stop
                stop_price = curr_close - stop_dist
                tp_dist = stop_dist * self.risk_reward_ratio
                tp_price = curr_close + tp_dist

                signals.append(SignalCandidate(
                    signal_id=f"SIG-BO-{timestamp_ms}-LONG",
                    strategy_id=self.metadata.strategy_id,
                    strategy_version=self.metadata.version,
                    timestamp=timestamp_ms,
                    symbol="ETHUSDT",
                    direction=SignalDirection.LONG,
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
                    evidence=[f"Close ({curr_close}) broke above {self.lookback_period}-bar high ({round(ch_high, 2)})"],
                    feature_snapshot={"channel_high": ch_high, "channel_low": ch_low, "atr": curr_atr},
                ))

            # Breakout Short
            elif curr_close < ch_low:
                stop_dist = curr_atr * self.atr_multiplier_stop
                stop_price = curr_close + stop_dist
                tp_dist = stop_dist * self.risk_reward_ratio
                tp_price = curr_close - tp_dist

                signals.append(SignalCandidate(
                    signal_id=f"SIG-BO-{timestamp_ms}-SHORT",
                    strategy_id=self.metadata.strategy_id,
                    strategy_version=self.metadata.version,
                    timestamp=timestamp_ms,
                    symbol="ETHUSDT",
                    direction=SignalDirection.SHORT,
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
                    evidence=[f"Close ({curr_close}) broke below {self.lookback_period}-bar low ({round(ch_low, 2)})"],
                    feature_snapshot={"channel_high": ch_high, "channel_low": ch_low, "atr": curr_atr},
                ))

        return signals
