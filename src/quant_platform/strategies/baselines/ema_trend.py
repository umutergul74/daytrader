"""EMA Trend Following Baseline Strategy."""

from typing import List, Dict, Any, Optional
import polars as pl

from quant_platform.domain.signal import (
    SignalCandidate,
    SignalDirection,
    SignalType,
    StopCandidate,
    TargetCandidate,
)
from quant_platform.features.indicators.trend import compute_ema
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class EmaTrendStrategy(BaseStrategy):
    """Simple, transparent trend-following baseline using Fast/Slow EMA with ATR stop/target."""

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        atr_period: int = 14,
        atr_multiplier_stop: float = 2.0,
        risk_reward_ratio: float = 2.0,
    ):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.atr_period = atr_period
        self.atr_multiplier_stop = atr_multiplier_stop
        self.risk_reward_ratio = risk_reward_ratio

        metadata = StrategyMetadata(
            strategy_id="baseline:ema_trend:v1",
            version="v1",
            hypothesis="Asset displays medium-term price momentum when fast EMA crosses above/below slow EMA with ATR-normalized risk.",
            required_features=["technical:ema:v1", "technical:atr:v1"],
            parameters={
                "fast_period": fast_period,
                "slow_period": slow_period,
                "atr_period": atr_period,
                "atr_multiplier_stop": atr_multiplier_stop,
                "risk_reward_ratio": risk_reward_ratio,
            },
        )
        super().__init__(metadata)

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        """Generate trend signals on crossover/trend continuation."""
        if len(df) < max(self.slow_period, self.atr_period) + 5:
            return []

        # 1. Compute required indicators
        fast_col = f"ema_{self.fast_period}"
        slow_col = f"ema_{self.slow_period}"
        atr_col = f"atr_{self.atr_period}"

        df_calc = compute_ema(df, period=self.fast_period, output_col=fast_col)
        df_calc = compute_ema(df_calc, period=self.slow_period, output_col=slow_col)
        df_calc = compute_atr(df_calc, period=self.atr_period, output_col=atr_col)

        # 2. Iterate causally through rows
        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        prev_row: Optional[Dict[str, Any]] = None
        for i, row in enumerate(rows):
            if i < self.slow_period + 2:
                prev_row = row
                continue

            prev_fast = prev_row[fast_col]
            prev_slow = prev_row[slow_col]
            curr_fast = row[fast_col]
            curr_slow = row[slow_col]
            curr_atr = row[atr_col]
            curr_close = row["close"]
            timestamp_ms = int(row["open_time"])

            if curr_atr is None or curr_atr <= 0 or curr_fast is None or curr_slow is None:
                prev_row = row
                continue

            # Bullish crossover: Fast crosses above Slow
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                stop_dist = curr_atr * self.atr_multiplier_stop
                stop_price = curr_close - stop_dist
                tp_dist = stop_dist * self.risk_reward_ratio
                tp_price = curr_close + tp_dist

                signal = SignalCandidate(
                    signal_id=f"SIG-EMA-{timestamp_ms}-LONG",
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
                        description=f"{self.atr_multiplier_stop}x ATR({self.atr_period})",
                    ),
                    target_candidates=[
                        TargetCandidate(
                            name="TP1",
                            price=round(tp_price, 2),
                            reward_r=self.risk_reward_ratio,
                            description=f"{self.risk_reward_ratio}R Target",
                        )
                    ],
                    calculated_rr=self.risk_reward_ratio,
                    evidence=[
                        f"Fast EMA({self.fast_period}) crossed above Slow EMA({self.slow_period})",
                        f"Close ({curr_close}) above Fast EMA ({round(curr_fast, 2)})",
                    ],
                    feature_snapshot={
                        "fast_ema": curr_fast,
                        "slow_ema": curr_slow,
                        "atr": curr_atr,
                    },
                )
                signals.append(signal)

            # Bearish crossover: Fast crosses below Slow
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                stop_dist = curr_atr * self.atr_multiplier_stop
                stop_price = curr_close + stop_dist
                tp_dist = stop_dist * self.risk_reward_ratio
                tp_price = curr_close - tp_dist

                signal = SignalCandidate(
                    signal_id=f"SIG-EMA-{timestamp_ms}-SHORT",
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
                        description=f"{self.atr_multiplier_stop}x ATR({self.atr_period})",
                    ),
                    target_candidates=[
                        TargetCandidate(
                            name="TP1",
                            price=round(tp_price, 2),
                            reward_r=self.risk_reward_ratio,
                            description=f"{self.risk_reward_ratio}R Target",
                        )
                    ],
                    calculated_rr=self.risk_reward_ratio,
                    evidence=[
                        f"Fast EMA({self.fast_period}) crossed below Slow EMA({self.slow_period})",
                        f"Close ({curr_close}) below Fast EMA ({round(curr_fast, 2)})",
                    ],
                    feature_snapshot={
                        "fast_ema": curr_fast,
                        "slow_ema": curr_slow,
                        "atr": curr_atr,
                    },
                )
                signals.append(signal)

            prev_row = row

        return signals
