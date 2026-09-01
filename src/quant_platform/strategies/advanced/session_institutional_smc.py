"""Institutional Multi-Timeframe Session SMC Strategy.

Combines:
1. Session Killzone Timing (London 07:00-12:00 UTC, NY 12:00-20:00 UTC)
2. Macro Trend Bias Filter (EMA 50 / 200 Structural Alignment)
3. Dual-Setup Engine:
   - Setup A (Reversal): Liquidity Sweep of Key Swing / Session Lows + FVG Mitigation
   - Setup B (Continuation): Trend-aligned Break of Structure (BOS) + FVG Pullback
4. Asymmetric Risk-Reward (2.2R - 2.5R) with Structural ATR Stop Loss
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
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
from quant_platform.features.smc.fvg import FvgEngine
from quant_platform.features.smc.liquidity import LiquidityEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class SessionInstitutionalSMCStrategy(BaseStrategy):
    """Institutional Grade Session SMC Trading Strategy for ETHUSDT Futures."""

    def __init__(
        self,
        left_bars: int = 3,
        right_bars: int = 3,
        atr_period: int = 14,
        fast_ema: int = 50,
        slow_ema: int = 200,
        min_gap_atr_ratio: float = 0.10,
        risk_reward_ratio: float = 2.2,
        allowed_hours_utc: Optional[List[int]] = None,
    ):
        self.left_bars = left_bars
        self.right_bars = right_bars
        self.atr_period = atr_period
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.min_gap_atr_ratio = min_gap_atr_ratio
        self.risk_reward_ratio = risk_reward_ratio
        # Default: London (07-12 UTC) + NY (12-20 UTC)
        self.allowed_hours_utc = allowed_hours_utc or list(range(7, 21))

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="smc:session_institutional:v1",
            version="v1",
            family="smc",
            hypothesis=(
                "Institutional order flow concentrates during London/NY sessions. "
                "Trading liquidity sweep reversals and trend-aligned FVG continuation pullbacks "
                "with structural invalidations yields persistent alpha."
            ),
            parameters={
                "left_bars": self.left_bars,
                "right_bars": self.right_bars,
                "atr_period": self.atr_period,
                "fast_ema": self.fast_ema,
                "slow_ema": self.slow_ema,
                "min_gap_atr_ratio": self.min_gap_atr_ratio,
                "risk_reward_ratio": self.risk_reward_ratio,
                "allowed_hours_utc": self.allowed_hours_utc,
            },
            required_features=[
                "smc:liquidity_sweep",
                "smc:fvg_three_candle",
                "trend:ema",
                "volatility:atr",
            ],
        )

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        if df.is_empty():
            return []

        # 1. Compute Indicators
        atr_col = f"atr_{self.atr_period}"
        fast_col = f"ema_{self.fast_ema}"
        slow_col = f"ema_{self.slow_ema}"

        df_calc = compute_atr(df, period=self.atr_period, output_col=atr_col)
        df_calc = compute_ema(df_calc, period=self.fast_ema, output_col=fast_col)
        df_calc = compute_ema(df_calc, period=self.slow_ema, output_col=slow_col)

        # 2. SMC Sweeps and FVGs
        df_calc, _ = LiquidityEngine.detect_liquidity_sweeps(
            df_calc,
            left_bars=self.left_bars,
            right_bars=self.right_bars,
            atr_period=self.atr_period,
        )
        df_calc, _ = FvgEngine.detect_and_track_fvgs(
            df_calc,
            atr_period=self.atr_period,
            min_gap_atr_ratio=self.min_gap_atr_ratio,
        )

        signals: List[SignalCandidate] = []
        rows = df_calc.iter_rows(named=True)

        recent_bull_sweep = 0
        recent_bear_sweep = 0
        last_sweep_low = 0.0
        last_sweep_high = 0.0

        for row in rows:
            open_time_ms = int(row["open_time"])
            close_time_ms = int(row.get("close_time", open_time_ms + 900000 - 1))
            
            # UTC hour extraction
            hour_utc = (open_time_ms // 3600000) % 24
            is_session_active = hour_utc in self.allowed_hours_utc

            close_p = float(row["close"])
            open_p = float(row["open"])
            high_p = float(row["high"])
            low_p = float(row["low"])
            atr_val = float(row[atr_col]) if row[atr_col] is not None else (close_p * 0.005)
            ema_fast_val = float(row[fast_col]) if row[fast_col] is not None else close_p
            ema_slow_val = float(row[slow_col]) if row[slow_col] is not None else close_p

            is_sell_rec = row.get("is_sellside_reclaim", False)
            is_buy_rec = row.get("is_buyside_reclaim", False)
            is_inside_bull_fvg = row.get("is_inside_bullish_fvg", False)
            is_inside_bear_fvg = row.get("is_inside_bearish_fvg", False)

            # Update sweep memory (active for 8 bars)
            if is_sell_rec:
                recent_bull_sweep = 8
                last_sweep_low = low_p
            else:
                recent_bull_sweep = max(0, recent_bull_sweep - 1)

            if is_buy_rec:
                recent_bear_sweep = 8
                last_sweep_high = high_p
            else:
                recent_bear_sweep = max(0, recent_bear_sweep - 1)

            if not is_session_active or atr_val <= 0:
                continue

            # Trend Filter
            is_uptrend = ema_fast_val >= ema_slow_val
            is_downtrend = ema_fast_val < ema_slow_val

            # ----------------------------------------------------
            # Setup 1: Liquidity Sweep Reversal (Judas Swing)
            # ----------------------------------------------------
            # Bullish Reversal: Sellside liquidity swept + price pulls into active Bullish FVG
            if recent_bull_sweep > 0 and is_inside_bull_fvg and not (close_p < ema_slow_val * 0.96):
                sweep_ref = last_sweep_low if last_sweep_low > 0 else low_p
                stop_p = min(sweep_ref, low_p) - (0.3 * atr_val)
                risk_dist = close_p - stop_p
                if risk_dist > (0.2 * atr_val):
                    tp_p = close_p + (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-INST-SWP-BULL-{open_time_ms}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=open_time_ms,
                        direction=SignalDirection.LONG,
                        entry_type=SignalType.MARKET,
                        entry_price=close_p,
                        stop_candidate=StopCandidate(name="SWEEP_LOW_SL", price=stop_p, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                        evidence=["Session active", "Sell-side sweep reclaim", "Bullish FVG mitigation retest"],
                    ))
                    recent_bull_sweep = 0  # consume trigger
                    continue

            # Bearish Reversal: Buyside liquidity swept + price pulls into active Bearish FVG
            elif recent_bear_sweep > 0 and is_inside_bear_fvg and not (close_p > ema_slow_val * 1.04):
                sweep_ref = last_sweep_high if last_sweep_high > 0 else high_p
                stop_p = max(sweep_ref, high_p) + (0.3 * atr_val)
                risk_dist = stop_p - close_p
                if risk_dist > (0.2 * atr_val):
                    tp_p = close_p - (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-INST-SWP-BEAR-{open_time_ms}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=open_time_ms,
                        direction=SignalDirection.SHORT,
                        entry_type=SignalType.MARKET,
                        entry_price=close_p,
                        stop_candidate=StopCandidate(name="SWEEP_HIGH_SL", price=stop_p, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                        evidence=["Session active", "Buy-side sweep reclaim", "Bearish FVG mitigation retest"],
                    ))
                    recent_bear_sweep = 0
                    continue

            # ----------------------------------------------------
            # Setup 2: Institutional Trend Continuation (FVG Pullback in Trend)
            # ----------------------------------------------------
            # Bullish Continuation: Strong uptrend + price touches bullish FVG and closes green
            if is_uptrend and close_p > ema_fast_val and is_inside_bull_fvg and close_p > open_p:
                stop_p = low_p - (0.4 * atr_val)
                risk_dist = close_p - stop_p
                if risk_dist > (0.3 * atr_val):
                    tp_p = close_p + (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-INST-CONT-BULL-{open_time_ms}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=open_time_ms,
                        direction=SignalDirection.LONG,
                        entry_type=SignalType.MARKET,
                        entry_price=close_p,
                        stop_candidate=StopCandidate(name="CONT_PULLBACK_SL", price=stop_p, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                        evidence=["Session active", "EMA Uptrend aligned", "FVG Continuation rejection close"],
                    ))
                    continue

            # Bearish Continuation: Strong downtrend + price touches bearish FVG and closes red
            elif is_downtrend and close_p < ema_fast_val and is_inside_bear_fvg and close_p < open_p:
                stop_p = high_p + (0.4 * atr_val)
                risk_dist = stop_p - close_p
                if risk_dist > (0.3 * atr_val):
                    tp_p = close_p - (self.risk_reward_ratio * risk_dist)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-INST-CONT-BEAR-{open_time_ms}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=open_time_ms,
                        direction=SignalDirection.SHORT,
                        entry_type=SignalType.MARKET,
                        entry_price=close_p,
                        stop_candidate=StopCandidate(name="CONT_PULLBACK_SL", price=stop_p, risk_distance=risk_dist),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                        evidence=["Session active", "EMA Downtrend aligned", "FVG Continuation rejection close"],
                    ))
                    continue

        return signals
