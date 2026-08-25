"""Regime-Aware RSI Mean Reversion Strategy."""

from typing import List, Optional
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
from quant_platform.regimes.engine import MarketRegimeEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class RegimeAwareMeanReversionStrategy(BaseStrategy):
    """Executes RSI mean reversion strictly within RANGING or COMPRESSION market regimes."""

    def __init__(
        self,
        rsi_period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        atr_multiplier_stop: float = 1.5,
        risk_reward_ratio: float = 2.0,
    ):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.atr_multiplier_stop = atr_multiplier_stop
        self.risk_reward_ratio = risk_reward_ratio

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="regime:rsi_mean_reversion",
            version="v1",
            family="regime_filtered",
            hypothesis="Filtering RSI mean-reversion signals by causal market regime eliminates trend-exhaustion false signals.",
            parameters={
                "rsi_period": self.rsi_period,
                "oversold": self.oversold,
                "overbought": self.overbought,
                "atr_multiplier_stop": self.atr_multiplier_stop,
                "risk_reward_ratio": self.risk_reward_ratio,
            },
            required_features=["momentum:rsi", "regime:rules", "volatility:atr"],
        )

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        rsi_col = f"rsi_{self.rsi_period}"
        df_calc = compute_rsi(df, period=self.rsi_period, output_col=rsi_col)
        df_calc = compute_atr(df_calc, period=14, output_col="atr_14")
        df_calc = MarketRegimeEngine.classify_regimes(df_calc)

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        for i, row in enumerate(rows):
            if i == 0:
                continue

            r_state = row["regime_state"]
            r_vol = row["regime_volatility"]
            rsi_val = row[rsi_col]
            atr_val = row["atr_14"]
            close = row["close"]

            if rsi_val is None or atr_val is None:
                continue

            # Only activate in RANGING or COMPRESSION, and not EXTREME volatility
            if r_state not in ["RANGING", "COMPRESSION"] or r_vol == "EXTREME":
                continue

            # Long signal on oversold
            if rsi_val <= self.oversold:
                stop_dist = self.atr_multiplier_stop * atr_val
                stop_price = close - stop_dist
                tp_price = close + (self.risk_reward_ratio * stop_dist)

                signals.append(SignalCandidate(
                    signal_id=f"SIG-REG-RSI-LONG-{row['open_time']}",
                    strategy_id=self.metadata.strategy_id,
                    strategy_version=self.metadata.version,
                    timestamp=row["close_time"],
                    direction=SignalDirection.LONG,
                    entry_price=close,
                    stop_candidate=StopCandidate(name="ATR_STOP", price=stop_price, risk_distance=stop_dist),
                    target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                    calculated_rr=self.risk_reward_ratio,
                ))

            # Short signal on overbought
            elif rsi_val >= self.overbought:
                stop_dist = self.atr_multiplier_stop * atr_val
                stop_price = close + stop_dist
                tp_price = close - (self.risk_reward_ratio * stop_dist)

                signals.append(SignalCandidate(
                    signal_id=f"SIG-REG-RSI-SHORT-{row['open_time']}",
                    strategy_id=self.metadata.strategy_id,
                    strategy_version=self.metadata.version,
                    timestamp=row["close_time"],
                    direction=SignalDirection.SHORT,
                    entry_price=close,
                    stop_candidate=StopCandidate(name="ATR_STOP", price=stop_price, risk_distance=stop_dist),
                    target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                    calculated_rr=self.risk_reward_ratio,
                ))

        return signals
