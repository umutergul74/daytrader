"""RSI Mean Reversion Baseline Strategy."""

from typing import List, Dict, Any, Optional
import polars as pl

from quant_platform.domain.signal import (
    SignalCandidate,
    SignalDirection,
    SignalType,
    StopCandidate,
    TargetCandidate,
)
from quant_platform.features.indicators.momentum import compute_rsi
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class RsiMeanReversionStrategy(BaseStrategy):
    """Mean reversion baseline using RSI extremes (<30 oversold, >70 overbought)."""

    def __init__(
        self,
        rsi_period: int = 14,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
        atr_period: int = 14,
        atr_multiplier_stop: float = 1.5,
        risk_reward_ratio: float = 1.5,
    ):
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.atr_period = atr_period
        self.atr_multiplier_stop = atr_multiplier_stop
        self.risk_reward_ratio = risk_reward_ratio

        metadata = StrategyMetadata(
            strategy_id="baseline:rsi_reversion:v1",
            version="v1",
            hypothesis="Asset mean-reverts when RSI reaches oversold (<30) or overbought (>70) levels.",
            required_features=["technical:rsi:v1", "technical:atr:v1"],
            parameters={
                "rsi_period": rsi_period,
                "oversold_threshold": oversold_threshold,
                "overbought_threshold": overbought_threshold,
                "atr_period": atr_period,
                "atr_multiplier_stop": atr_multiplier_stop,
                "risk_reward_ratio": risk_reward_ratio,
            },
        )
        super().__init__(metadata)

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        if len(df) < max(self.rsi_period, self.atr_period) + 5:
            return []

        rsi_col = f"rsi_{self.rsi_period}"
        atr_col = f"atr_{self.atr_period}"

        df_calc = compute_rsi(df, period=self.rsi_period, output_col=rsi_col)
        df_calc = compute_atr(df_calc, period=self.atr_period, output_col=atr_col)

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        prev_row: Optional[Dict[str, Any]] = None
        for i, row in enumerate(rows):
            if i < self.rsi_period + 2:
                prev_row = row
                continue

            prev_rsi = prev_row[rsi_col]
            curr_rsi = row[rsi_col]
            curr_atr = row[atr_col]
            curr_close = row["close"]
            timestamp_ms = int(row["open_time"])

            if curr_rsi is None or curr_atr is None or curr_atr <= 0:
                prev_row = row
                continue

            # Oversold exit/bounce: RSI was below threshold, now crosses back above
            if prev_rsi <= self.oversold_threshold and curr_rsi > self.oversold_threshold:
                stop_dist = curr_atr * self.atr_multiplier_stop
                stop_price = curr_close - stop_dist
                tp_dist = stop_dist * self.risk_reward_ratio
                tp_price = curr_close + tp_dist

                signal = SignalCandidate(
                    signal_id=f"SIG-RSI-{timestamp_ms}-LONG",
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
                            description=f"{self.risk_reward_ratio}R Mean Reversion Target",
                        )
                    ],
                    calculated_rr=self.risk_reward_ratio,
                    evidence=[
                        f"RSI({self.rsi_period}) crossed above oversold ({self.oversold_threshold}) to {round(curr_rsi, 2)}",
                    ],
                    feature_snapshot={"rsi": curr_rsi, "atr": curr_atr},
                )
                signals.append(signal)

            # Overbought exit/reversal: RSI was above threshold, now crosses back below
            elif prev_rsi >= self.overbought_threshold and curr_rsi < self.overbought_threshold:
                stop_dist = curr_atr * self.atr_multiplier_stop
                stop_price = curr_close + stop_dist
                tp_dist = stop_dist * self.risk_reward_ratio
                tp_price = curr_close - tp_dist

                signal = SignalCandidate(
                    signal_id=f"SIG-RSI-{timestamp_ms}-SHORT",
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
                            description=f"{self.risk_reward_ratio}R Mean Reversion Target",
                        )
                    ],
                    calculated_rr=self.risk_reward_ratio,
                    evidence=[
                        f"RSI({self.rsi_period}) crossed below overbought ({self.overbought_threshold}) to {round(curr_rsi, 2)}",
                    ],
                    feature_snapshot={"rsi": curr_rsi, "atr": curr_atr},
                )
                signals.append(signal)

            prev_row = row

        return signals
