"""Institutional Macro Structure Champion Strategy for ETHUSDT Futures.

Architecture:
1. 4H Macro Structural Trend Filter (Delayed confirmation causal swing breaks)
2. 1H Dynamic Pullback Zone (EMA 20 rejection & continuation bounce)
3. Structural Swing Invalidation with ATR Cushion (Zero lookahead)
4. Asymmetric Risk-Reward (2.4R) with fixed risk position sizing
5. Session Volatility Filter (London 07:00-12:00 UTC & NY 12:00-21:00 UTC)
"""

from typing import List, Optional, Dict, Any
import polars as pl

from quant_platform.domain.signal import (
    SignalCandidate,
    SignalDirection,
    SignalType,
    StopCandidate,
    TargetCandidate,
)
from quant_platform.data.timeframes.resampler import CausalResampler
from quant_platform.features.indicators.trend import compute_ema
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.features.structure.market_structure import MarketStructureEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class InstitutionalMacroStructureChampion(BaseStrategy):
    """Production Champion Strategy for ETHUSDT Futures."""

    def __init__(
        self,
        h4_left_bars: int = 5,
        h4_right_bars: int = 5,
        h1_left_bars: int = 5,
        h1_right_bars: int = 5,
        h1_ema_pull: int = 20,
        risk_reward_ratio: float = 2.4,
        stop_atr_cushion: float = 0.5,
        use_session_filter: bool = True,
    ):
        self.h4_left_bars = h4_left_bars
        self.h4_right_bars = h4_right_bars
        self.h1_left_bars = h1_left_bars
        self.h1_right_bars = h1_right_bars
        self.h1_ema_pull = h1_ema_pull
        self.risk_reward_ratio = risk_reward_ratio
        self.stop_atr_cushion = stop_atr_cushion
        self.use_session_filter = use_session_filter

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="structure:macro_champion",
            version="v1",
            family="structure",
            hypothesis=(
                "Institutional crypto momentum flows along 4H macro structure. "
                "1H EMA pullbacks with structural invalidations capture high-R expansion moves."
            ),
            parameters={
                "h4_left_bars": self.h4_left_bars,
                "h4_right_bars": self.h4_right_bars,
                "h1_left_bars": self.h1_left_bars,
                "h1_right_bars": self.h1_right_bars,
                "h1_ema_pull": self.h1_ema_pull,
                "risk_reward_ratio": self.risk_reward_ratio,
                "stop_atr_cushion": self.stop_atr_cushion,
                "use_session_filter": self.use_session_filter,
            },
            required_features=["structure:bos_choch", "trend:ema", "volatility:atr"],
        )

    def generate_signals(self, df_1h: pl.DataFrame) -> List[SignalCandidate]:
        if df_1h.is_empty():
            return []

        # 1. Resample to 4H for Macro Structural Trend
        df_4h = CausalResampler.resample(df_1h, target_timeframe="4h")
        df_4h = MarketStructureEngine.compute_market_structure(
            df_4h, left_bars=self.h4_left_bars, right_bars=self.h4_right_bars
        )
        df_4h = compute_ema(df_4h, period=20, output_col="h4_ema_20")

        # Causal Join of 4H Macro Trend onto 1H
        df_4h_feat = df_4h.select([
            pl.col("close_time").alias("h4_close_time"),
            pl.col("structural_trend").alias("h4_trend"),
            pl.col("h4_ema_20"),
        ])

        # 2. Compute 1H Features
        pull_col = f"ema_{self.h1_ema_pull}"
        df_calc = compute_ema(df_1h, period=self.h1_ema_pull, output_col=pull_col)
        df_calc = compute_atr(df_calc, period=14, output_col="h1_atr")
        df_calc = MarketStructureEngine.compute_market_structure(
            df_calc, left_bars=self.h1_left_bars, right_bars=self.h1_right_bars
        )

        df_joined = df_calc.join_asof(
            df_4h_feat,
            left_on="open_time",
            right_on="h4_close_time",
            strategy="backward",
        )

        signals: List[SignalCandidate] = []
        rows = df_joined.iter_rows(named=True)
        sh_col = f"last_sh_L{self.h1_left_bars}_R{self.h1_right_bars}"
        sl_col = f"last_sl_L{self.h1_left_bars}_R{self.h1_right_bars}"

        for r in rows:
            open_time = int(r["open_time"])
            hour_utc = (open_time // 3600000) % 24

            if self.use_session_filter and not (7 <= hour_utc < 21):
                continue

            h4_tr = r["h4_trend"]
            h1_tr = r["structural_trend"]

            close = float(r["close"])
            open_p = float(r["open"])
            low = float(r["low"])
            high = float(r["high"])

            ema_pull = float(r[pull_col]) if r[pull_col] is not None else close
            atr = float(r["h1_atr"]) if r["h1_atr"] is not None else (close * 0.005)
            last_sh = float(r[sh_col]) if r[sh_col] is not None else high
            last_sl = float(r[sl_col]) if r[sl_col] is not None else low

            # Bullish Setup:
            # - 4H Trend is Bullish or Neutral (h4_tr is None or h4_tr >= 0)
            # - 1H Trend is Bullish (h1_tr == 1)
            # - 1H Low tested EMA20 pullback zone, 1H Close closed green above EMA20
            if (h4_tr is None or h4_tr >= 0) and h1_tr == 1:
                if low <= ema_pull and close > ema_pull and close > open_p:
                    stop_p = last_sl if last_sl < close else (low - (self.stop_atr_cushion * atr))
                    if stop_p >= close:
                        stop_p = close - (1.0 * atr)

                    risk_d = close - stop_p
                    if (0.3 * atr) <= risk_d <= (3.5 * atr):
                        tp_p = close + (self.risk_reward_ratio * risk_d)
                        signals.append(SignalCandidate(
                            signal_id=f"SIG-CHAMP-BULL-{open_time}",
                            strategy_id=self.metadata.strategy_id,
                            strategy_version=self.metadata.version,
                            timestamp=open_time,
                            direction=SignalDirection.LONG,
                            entry_type=SignalType.MARKET,
                            entry_price=close,
                            stop_candidate=StopCandidate(name="STRUCTURAL_SL", price=stop_p, risk_distance=risk_d),
                            target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                            calculated_rr=self.risk_reward_ratio,
                            evidence=["4H Macro Bullish", "1H Structure Bullish", "1H EMA20 Pullback rejection"],
                        ))

            # Bearish Setup:
            # - 4H Trend is Bearish or Neutral (h4_tr is None or h4_tr <= 0)
            # - 1H Trend is Bearish (h1_tr == -1)
            # - 1H High tested EMA20 pullback zone, 1H Close closed red below EMA20
            elif (h4_tr is None or h4_tr <= 0) and h1_tr == -1:
                if high >= ema_pull and close < ema_pull and close < open_p:
                    stop_p = last_sh if last_sh > close else (high + (self.stop_atr_cushion * atr))
                    if stop_p <= close:
                        stop_p = close + (1.0 * atr)

                    risk_d = stop_p - close
                    if (0.3 * atr) <= risk_d <= (3.5 * atr):
                        tp_p = close - (self.risk_reward_ratio * risk_d)
                        signals.append(SignalCandidate(
                            signal_id=f"SIG-CHAMP-BEAR-{open_time}",
                            strategy_id=self.metadata.strategy_id,
                            strategy_version=self.metadata.version,
                            timestamp=open_time,
                            direction=SignalDirection.SHORT,
                            entry_type=SignalType.MARKET,
                            entry_price=close,
                            stop_candidate=StopCandidate(name="STRUCTURAL_SL", price=stop_p, risk_distance=risk_d),
                            target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                            calculated_rr=self.risk_reward_ratio,
                            evidence=["4H Macro Bearish", "1H Structure Bearish", "1H EMA20 Pullback rejection"],
                        ))

        return signals
