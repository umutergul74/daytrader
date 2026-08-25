"""Market Structure Trend Continuation Strategy."""

from typing import List, Optional
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
from quant_platform.features.structure.market_structure import MarketStructureEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class StructureContinuationStrategy(BaseStrategy):
    """Trades pullbacks in confirmed structural trends with structural invalidation."""

    def __init__(
        self,
        left_bars: int = 5,
        right_bars: int = 5,
        ema_pullback_period: int = 20,
        atr_period: int = 14,
        risk_reward_ratio: float = 2.0,
    ):
        self.left_bars = left_bars
        self.right_bars = right_bars
        self.ema_pullback_period = ema_pullback_period
        self.atr_period = atr_period
        self.risk_reward_ratio = risk_reward_ratio

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="structure:continuation",
            version="v1",
            family="structure",
            hypothesis="Pullbacks in direction of confirmed higher-timeframe structural trend have positive statistical expectancy.",
            parameters={
                "left_bars": self.left_bars,
                "right_bars": self.right_bars,
                "ema_pullback_period": self.ema_pullback_period,
                "atr_period": self.atr_period,
                "risk_reward_ratio": self.risk_reward_ratio,
            },
            required_features=["structure:bos_choch", "trend:ema", "volatility:atr"],
        )

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        ema_col = f"ema_{self.ema_pullback_period}"
        atr_col = f"atr_{self.atr_period}"

        df_calc = compute_ema(df, period=self.ema_pullback_period, output_col=ema_col)
        df_calc = compute_atr(df_calc, period=self.atr_period, output_col=atr_col)
        df_calc = MarketStructureEngine.compute_market_structure(df_calc, left_bars=self.left_bars, right_bars=self.right_bars)

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        for row in rows:
            trend = row["structural_trend"]
            close = row["close"]
            low = row["low"]
            high = row["high"]
            ema_val = row[ema_col]
            atr_val = row[atr_col]
            last_sh = row[f"last_sh_L{self.left_bars}_R{self.right_bars}"]
            last_sl = row[f"last_sl_L{self.left_bars}_R{self.right_bars}"]

            if ema_val is None or atr_val is None or last_sh is None or last_sl is None:
                continue

            # Bullish Continuation: In Bullish trend (1), price dipped to EMA and bounced
            if trend == 1 and low <= ema_val and close > ema_val:
                stop_price = float(last_sl) if last_sl < close else close - (1.5 * atr_val)
                risk_dist = close - stop_price
                if risk_dist > 0:
                    tp_price = close + (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-STR-BULL-{row['open_time']}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=row["close_time"],
                        direction=SignalDirection.LONG,
                        entry_price=close,
                        stop_candidate=StopCandidate(name="STRUCTURAL_SL", price=stop_price, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                    ))

            # Bearish Continuation: In Bearish trend (-1), price pulled up to EMA and rejected
            elif trend == -1 and high >= ema_val and close < ema_val:
                stop_price = float(last_sh) if last_sh > close else close + (1.5 * atr_val)
                risk_dist = stop_price - close
                if risk_dist > 0:
                    tp_price = close - (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-STR-BEAR-{row['open_time']}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=row["close_time"],
                        direction=SignalDirection.SHORT,
                        entry_price=close,
                        stop_candidate=StopCandidate(name="STRUCTURAL_SL", price=stop_price, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_price, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                    ))

        return signals
