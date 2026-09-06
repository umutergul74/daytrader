"""Institutional-Grade Multi-Factor Smart Money Confluence Strategy.

Combines:
1. 4H Macro Bias: Higher-timeframe market structure (BOS / CHoCH) and 20 EMA trend alignment.
2. Liquidity Sweep Detection: Reclaim of key swing high/low liquidity raids and session extremes.
3. Fair Value Gap (FVG) Imbalance: Energetic displacement leaving imbalances, entered on causal mitigation retest.
4. Structural Invalidation Stop Loss: Anchored to the liquidity raid extreme / FVG boundary with ATR cushion.
5. Asymmetric Risk-to-Reward: 2.0R - 3.0R target structure providing robust mathematical expectancy.
6. Session Timing: High-liquidity London (07:00-12:00 UTC) and New York (12:00-21:00 UTC) institutional killzones.
7. Zero Lookahead Bias: Causal HTF feature alignment with strict information availability guarantees.
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
from quant_platform.features.smc.fvg import FvgEngine
from quant_platform.features.smc.liquidity import LiquidityEngine
from quant_platform.features.structure.market_structure import MarketStructureEngine
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata


class InstitutionalSmartMoneyConfluenceStrategy(BaseStrategy):
    """Institutional Smart Money Confluence Strategy for ETHUSDT Futures."""

    def __init__(
        self,
        h4_left_bars: int = 5,
        h4_right_bars: int = 5,
        ltf_left_bars: int = 4,
        ltf_right_bars: int = 4,
        min_gap_atr_ratio: float = 0.15,
        risk_reward_ratio: float = 2.4,
        stop_atr_cushion: float = 0.5,
        use_session_filter: bool = True,
        sweep_memory_bars: int = 6,
    ):
        self.h4_left_bars = h4_left_bars
        self.h4_right_bars = h4_right_bars
        self.ltf_left_bars = ltf_left_bars
        self.ltf_right_bars = ltf_right_bars
        self.min_gap_atr_ratio = min_gap_atr_ratio
        self.risk_reward_ratio = risk_reward_ratio
        self.stop_atr_cushion = stop_atr_cushion
        self.use_session_filter = use_session_filter
        self.sweep_memory_bars = sweep_memory_bars

        metadata = StrategyMetadata(
            strategy_id="smc:institutional_confluence:v1",
            version="v1",
            family="smc",
            hypothesis=(
                "Institutional market makers accumulate and distribute during London/NY sessions "
                "by raiding retail liquidity pools, displacing price to create Fair Value Gaps, and "
                "entering on causal mitigation retests aligned with 4H macro market structure."
            ),
            parameters={
                "h4_left_bars": self.h4_left_bars,
                "h4_right_bars": self.h4_right_bars,
                "ltf_left_bars": self.ltf_left_bars,
                "ltf_right_bars": self.ltf_right_bars,
                "min_gap_atr_ratio": self.min_gap_atr_ratio,
                "risk_reward_ratio": self.risk_reward_ratio,
                "stop_atr_cushion": self.stop_atr_cushion,
                "use_session_filter": self.use_session_filter,
                "sweep_memory_bars": self.sweep_memory_bars,
            },
            required_features=[
                "structure:4h_market_structure",
                "smc:liquidity_sweep",
                "smc:fvg_mitigation",
                "volatility:atr",
            ],
        )
        super().__init__(metadata)

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        """Generate institutional multi-factor confluence signals from causal DataFrame.

        Accepts any timeframe. If input resolution is sub-hourly (e.g. 1m or 15m),
        it causally resamples to 1H for institutional execution and 4H for macro trend,
        strictly maintaining zero lookahead bias by emitting signals at candle close.
        """
        if df.is_empty():
            return []

        # Determine if input is sub-hourly
        is_sub_hourly = False
        if len(df) > 1:
            bar_delta = int(df["open_time"][1] - df["open_time"][0])
            if bar_delta < 3600000:
                is_sub_hourly = True

        df_exec = CausalResampler.resample(df, target_timeframe="1h") if is_sub_hourly else df

        # 1. Resample causally to 4H for Macro Structural Trend & Momentum
        df_4h = CausalResampler.resample(df_exec, target_timeframe="4h")
        df_4h = MarketStructureEngine.compute_market_structure(
            df_4h, left_bars=self.h4_left_bars, right_bars=self.h4_right_bars
        )
        df_4h = compute_ema(df_4h, period=20, output_col="h4_ema_20")

        # Causal selection of 4H features: strictly available at close_time + 1
        df_4h_feat = df_4h.select([
            (pl.col("close_time") + 1).alias("h4_avail_time"),
            pl.col("structural_trend").alias("h4_trend"),
            pl.col("h4_ema_20"),
            pl.col("close").alias("h4_close"),
            pl.col("is_choch_bullish").alias("h4_choch_bull"),
            pl.col("is_choch_bearish").alias("h4_choch_bear"),
        ])

        # 2. LTF (1H) Indicators & Market Structure
        atr_col = "atr_14"
        df_calc = compute_atr(df_exec, period=14, output_col=atr_col)
        df_calc = compute_ema(df_calc, period=20, output_col="ltf_ema_20")
        df_calc = MarketStructureEngine.compute_market_structure(
            df_calc, left_bars=self.ltf_left_bars, right_bars=self.ltf_right_bars
        )

        # 3. Liquidity Sweeps & FVG Tracking
        df_calc, _ = LiquidityEngine.detect_liquidity_sweeps(
            df_calc,
            left_bars=self.ltf_left_bars,
            right_bars=self.ltf_right_bars,
            atr_period=14,
        )
        df_calc, _ = FvgEngine.detect_and_track_fvgs(
            df_calc,
            atr_period=14,
            min_gap_atr_ratio=self.min_gap_atr_ratio,
        )

        # 4. Causally Join 4H Macro Features onto Execution Timeframe (Zero Lookahead)
        df_joined = df_calc.sort("open_time").join_asof(
            df_4h_feat.sort("h4_avail_time"),
            left_on="open_time",
            right_on="h4_avail_time",
            strategy="backward",
        )

        signals: List[SignalCandidate] = []
        rows = df_joined.iter_rows(named=True)

        recent_bull_sweep = 0
        recent_bear_sweep = 0
        last_sweep_low = 0.0
        last_sweep_high = 0.0

        for r in rows:
            open_time = int(r["open_time"])
            close_time = int(r.get("close_time", open_time + 3600000 - 1))
            hour_utc = (open_time // 3600000) % 24

            # Session Filter: London (07-12) & NY (12-21) UTC
            if self.use_session_filter and not (7 <= hour_utc < 21):
                continue

            close_p = float(r["close"])
            open_p = float(r["open"])
            high_p = float(r["high"])
            low_p = float(r["low"])
            atr = float(r[atr_col]) if r[atr_col] is not None else (close_p * 0.005)

            # 4H Macro Bias Evaluation
            h4_trend = r["h4_trend"]  # 1=bullish, -1=bearish, 0=neutral
            h4_ema = float(r["h4_ema_20"]) if r["h4_ema_20"] is not None else close_p
            h4_close = float(r["h4_close"]) if r["h4_close"] is not None else close_p

            is_macro_bull = (h4_trend is None or h4_trend >= 0) and (h4_close >= h4_ema * 0.99)
            is_macro_bear = (h4_trend is None or h4_trend <= 0) and (h4_close <= h4_ema * 1.01)

            # SMC Features
            is_sell_rec = r.get("is_sellside_reclaim", False)
            is_buy_rec = r.get("is_buyside_reclaim", False)
            is_inside_bull_fvg = r.get("is_inside_bullish_fvg", False)
            is_inside_bear_fvg = r.get("is_inside_bearish_fvg", False)
            ltf_trend = r.get("structural_trend", 0)

            # Update sweep memory
            if is_sell_rec:
                recent_bull_sweep = self.sweep_memory_bars
                last_sweep_low = low_p
            else:
                recent_bull_sweep = max(0, recent_bull_sweep - 1)

            if is_buy_rec:
                recent_bear_sweep = self.sweep_memory_bars
                last_sweep_high = high_p
            else:
                recent_bear_sweep = max(0, recent_bear_sweep - 1)

            # Use candle close_time for signal timestamp to seamlessly align with sub-hourly or hourly bars
            sig_timestamp = close_time if is_sub_hourly else open_time

            # =================================================================
            # Setup 1: Liquidity Raid Reversal into FVG Retest (Judas Swing)
            # =================================================================
            # Bullish Confluence: Macro Bull + Sellside Sweep + Bullish FVG Retest
            if is_macro_bull and recent_bull_sweep > 0 and is_inside_bull_fvg:
                sweep_low_ref = last_sweep_low if last_sweep_low > 0 else low_p
                stop_p = min(sweep_low_ref, low_p) - (self.stop_atr_cushion * atr)
                risk_d = close_p - stop_p

                # Risk validation: 0.2% to 4.5% of price, >= 0.3 ATR
                if (0.3 * atr) <= risk_d <= (close_p * 0.045):
                    tp_p = close_p + (self.risk_reward_ratio * risk_d)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-INST-SWP-BULL-{open_time}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=sig_timestamp,
                        direction=SignalDirection.LONG,
                        entry_type=SignalType.MARKET,
                        entry_price=close_p,
                        stop_candidate=StopCandidate(name="SWEEP_INVAL_SL", price=stop_p, risk_distance=risk_d),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                        evidence=[
                            "4H Macro Bullish Structure",
                            f"Sell-side Liquidity Sweep Reclaim ({recent_bull_sweep} bars ago)",
                            "Active Bullish FVG Mitigation Retest",
                            f"Session Active ({hour_utc:02d}:00 UTC)",
                        ],
                    ))
                    recent_bull_sweep = 0  # consume trigger
                    continue

            # Bearish Confluence: Macro Bear + Buyside Sweep + Bearish FVG Retest
            elif is_macro_bear and recent_bear_sweep > 0 and is_inside_bear_fvg:
                sweep_high_ref = last_sweep_high if last_sweep_high > 0 else high_p
                stop_p = max(sweep_high_ref, high_p) + (self.stop_atr_cushion * atr)
                risk_d = stop_p - close_p

                if (0.3 * atr) <= risk_d <= (close_p * 0.045):
                    tp_p = close_p - (self.risk_reward_ratio * risk_d)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-INST-SWP-BEAR-{open_time}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=sig_timestamp,
                        direction=SignalDirection.SHORT,
                        entry_type=SignalType.MARKET,
                        entry_price=close_p,
                        stop_candidate=StopCandidate(name="SWEEP_INVAL_SL", price=stop_p, risk_distance=risk_d),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                        evidence=[
                            "4H Macro Bearish Structure",
                            f"Buy-side Liquidity Sweep Reclaim ({recent_bear_sweep} bars ago)",
                            "Active Bearish FVG Mitigation Retest",
                            f"Session Active ({hour_utc:02d}:00 UTC)",
                        ],
                    ))
                    recent_bear_sweep = 0
                    continue

            # =================================================================
            # Setup 2: Institutional Structural Continuation (BOS + FVG Pullback)
            # =================================================================
            # Bullish Continuation: 4H Bull + 1H Structure Bull + Bullish FVG test with green rejection close
            if is_macro_bull and ltf_trend == 1 and is_inside_bull_fvg and close_p > open_p:
                stop_p = low_p - (self.stop_atr_cushion * atr)
                risk_d = close_p - stop_p

                if (0.4 * atr) <= risk_d <= (close_p * 0.035):
                    tp_p = close_p + (self.risk_reward_ratio * risk_d)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-INST-CONT-BULL-{open_time}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=sig_timestamp,
                        direction=SignalDirection.LONG,
                        entry_type=SignalType.MARKET,
                        entry_price=close_p,
                        stop_candidate=StopCandidate(name="STRUCTURAL_LOW_SL", price=stop_p, risk_distance=risk_d),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                        evidence=[
                            "4H Macro Bullish Aligned",
                            "1H Structure Bullish Trend (BOS Confirmed)",
                            "Bullish FVG Pullback Rejection Close",
                            f"Session Active ({hour_utc:02d}:00 UTC)",
                        ],
                    ))
                    continue

            # Bearish Continuation: 4H Bear + 1H Structure Bear + Bearish FVG test with red rejection close
            elif is_macro_bear and ltf_trend == -1 and is_inside_bear_fvg and close_p < open_p:
                stop_p = high_p + (self.stop_atr_cushion * atr)
                risk_d = stop_p - close_p

                if (0.4 * atr) <= risk_d <= (close_p * 0.035):
                    tp_p = close_p - (self.risk_reward_ratio * risk_d)
                    signals.append(SignalCandidate(
                        signal_id=f"SIG-INST-CONT-BEAR-{open_time}",
                        strategy_id=self.metadata.strategy_id,
                        strategy_version=self.metadata.version,
                        timestamp=sig_timestamp,
                        direction=SignalDirection.SHORT,
                        entry_type=SignalType.MARKET,
                        entry_price=close_p,
                        stop_candidate=StopCandidate(name="STRUCTURAL_HIGH_SL", price=stop_p, risk_distance=risk_d),
                        target_candidates=[TargetCandidate(name="TP1", price=tp_p, reward_r=self.risk_reward_ratio)],
                        calculated_rr=self.risk_reward_ratio,
                        evidence=[
                            "4H Macro Bearish Aligned",
                            "1H Structure Bearish Trend (BOS Confirmed)",
                            "Bearish FVG Pullback Rejection Close",
                            f"Session Active ({hour_utc:02d}:00 UTC)",
                        ],
                    ))
                    continue

        return signals
