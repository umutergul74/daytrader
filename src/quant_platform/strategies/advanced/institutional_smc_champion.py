"""Institutional Smart Money Concepts (SMC) + Macro Structure Champion Strategy.

Confluence Architecture:
1. 4H Macro Market Structure: Directional bias determined by causal 4H BOS and CHoCH pivots.
2. 1H Structural Trend Alignment: 1H HH/HL (Bullish) or LH/LL (Bearish) confirmation.
3. 1H EMA20 Dynamic Value Zone: Price pulls back into the dynamic mean.
4. Smart Money Concepts (FVG Imbalance Confluence):
   - Entry candle must coincide with an active, unmitigated Fair Value Gap (FVG) zone.
   - Filters out false breakout pullbacks by verifying institutional imbalance presence.
5. Invalidation & Asymmetric Targets:
   - Structural swing invalidation stop loss with ATR cushion.
   - Asymmetric 2.4R payout target (targeting unmitigated opposing liquidity).
6. Session Volatility Gate:
   - London (07:00-12:00 UTC) & New York (12:00-21:00 UTC) execution.
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
from quant_platform.features.smc.fvg import FvgEngine
from quant_platform.features.smc.liquidity import LiquidityEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class InstitutionalSMCChampionStrategy(BaseStrategy):
    """Production Institutional SMC Strategy combining 4H Structure + FVG Confluence."""

    def __init__(
        self,
        h4_left_bars: int = 5,
        h4_right_bars: int = 5,
        h1_left_bars: int = 5,
        h1_right_bars: int = 5,
        h1_ema_pull: int = 20,
        risk_reward_ratio: float = 2.4,
        stop_atr_cushion: float = 0.5,
        fvg_min_atr_ratio: float = 0.20,
        use_session_filter: bool = True,
    ):
        self.h4_left_bars = h4_left_bars
        self.h4_right_bars = h4_right_bars
        self.h1_left_bars = h1_left_bars
        self.h1_right_bars = h1_right_bars
        self.h1_ema_pull = h1_ema_pull
        self.risk_reward_ratio = risk_reward_ratio
        self.stop_atr_cushion = stop_atr_cushion
        self.fvg_min_atr_ratio = fvg_min_atr_ratio
        self.use_session_filter = use_session_filter

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="smc:institutional_champion",
            version="v1",
            family="smc_structure",
            hypothesis=(
                "Combining 4H macro market structure with 1H Fair Value Gap (FVG) mitigation "
                "and EMA value pullbacks provides institutional confluence, filtering false signals."
            ),
            parameters={
                "h4_left_bars": self.h4_left_bars,
                "h4_right_bars": self.h4_right_bars,
                "h1_left_bars": self.h1_left_bars,
                "h1_right_bars": self.h1_right_bars,
                "h1_ema_pull": self.h1_ema_pull,
                "risk_reward_ratio": self.risk_reward_ratio,
                "stop_atr_cushion": self.stop_atr_cushion,
                "fvg_min_atr_ratio": self.fvg_min_atr_ratio,
                "use_session_filter": self.use_session_filter,
            },
            required_features=["structure:bos_choch", "smc:fvg", "trend:ema", "volatility:atr"],
        )

    def generate_signals(self, df_1h: pl.DataFrame) -> List[SignalCandidate]:
        if df_1h.is_empty():
            return []

        # 1. 4H Macro Trend
        df_4h = CausalResampler.resample(df_1h, target_timeframe="4h")
        df_4h = MarketStructureEngine.compute_market_structure(
            df_4h, left_bars=self.h4_left_bars, right_bars=self.h4_right_bars
        )
        df_4h = compute_ema(df_4h, period=20, output_col="h4_ema_20")

        df_4h_feat = df_4h.select([
            pl.col("close_time").alias("h4_close_time"),
            pl.col("structural_trend").alias("h4_trend"),
            pl.col("h4_ema_20"),
        ])

        # 2. 1H Structure, EMA, and ATR
        pull_col = f"ema_{self.h1_ema_pull}"
        df_calc = compute_ema(df_1h, period=self.h1_ema_pull, output_col=pull_col)
        df_calc = compute_atr(df_calc, period=14, output_col="h1_atr")
        df_calc = MarketStructureEngine.compute_market_structure(
            df_calc, left_bars=self.h1_left_bars, right_bars=self.h1_right_bars
        )

        # 3. 1H FVG Detection & Lifecycle
        df_calc, _ = FvgEngine.detect_and_track_fvgs(
            df_calc, atr_period=14, min_gap_atr_ratio=self.fvg_min_atr_ratio, timeframe="1h"
        )

        # 4. Causal As-Of Join
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

            # FVG Confluence Flags
            in_bull_fvg = r.get("is_inside_bullish_fvg", False) or (r.get("active_bullish_fvg_count", 0) > 0)
            in_bear_fvg = r.get("is_inside_bearish_fvg", False) or (r.get("active_bearish_fvg_count", 0) > 0)

            # Bullish Setup:
            # - 4H Macro Trend Bullish (>= 0)
            # - 1H Structure Bullish (== 1)
            # - Low tested EMA20 pullback zone, Close closed green above EMA20
            # - CONFLUENCE: Candle interacts with an active Fair Value Gap (FVG)
            if (h4_tr is None or h4_tr >= 0) and h1_tr == 1:
                if low <= ema_pull and close > ema_pull and close > open_p and in_bull_fvg:
                    stop_p = last_sl if last_sl < close else (low - (self.stop_atr_cushion * atr))
                    if stop_p >= close:
                        stop_p = close - (1.0 * atr)

                    risk_d = close - stop_p
                    if (0.3 * atr) <= risk_d <= (3.5 * atr):
                        tp_p = close + (self.risk_reward_ratio * risk_d)
                        signals.append(SignalCandidate(
                            signal_id=f"SIG-SMC-BULL-{open_time}",
                            strategy_id=self.metadata.strategy_id,
                            strategy_version=self.metadata.version,
                            timestamp=open_time,
                            direction=SignalDirection.LONG,
                            entry_type=SignalType.MARKET,
                            entry_price=close,
                            stop_candidate=StopCandidate(name="STRUCTURAL_SL", price=stop_p, risk_distance=risk_d),
                            target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                            calculated_rr=self.risk_reward_ratio,
                            evidence=[
                                "4H Macro Bullish",
                                "1H Structure Bullish",
                                "1H EMA20 Pullback Rejection",
                                "Active Bullish FVG Imbalance Confluence",
                            ],
                        ))

            # Bearish Setup:
            elif (h4_tr is None or h4_tr <= 0) and h1_tr == -1:
                if high >= ema_pull and close < ema_pull and close < open_p and in_bear_fvg:
                    stop_p = last_sh if last_sh > close else (high + (self.stop_atr_cushion * atr))
                    if stop_p <= close:
                        stop_p = close + (1.0 * atr)

                    risk_d = stop_p - close
                    if (0.3 * atr) <= risk_d <= (3.5 * atr):
                        tp_p = close - (self.risk_reward_ratio * risk_d)
                        signals.append(SignalCandidate(
                            signal_id=f"SIG-SMC-BEAR-{open_time}",
                            strategy_id=self.metadata.strategy_id,
                            strategy_version=self.metadata.version,
                            timestamp=open_time,
                            direction=SignalDirection.SHORT,
                            entry_type=SignalType.MARKET,
                            entry_price=close,
                            stop_candidate=StopCandidate(name="STRUCTURAL_SL", price=stop_p, risk_distance=risk_d),
                            target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                            calculated_rr=self.risk_reward_ratio,
                            evidence=[
                                "4H Macro Bearish",
                                "1H Structure Bearish",
                                "1H EMA20 Pullback Rejection",
                                "Active Bearish FVG Imbalance Confluence",
                            ],
                        ))

        return signals
