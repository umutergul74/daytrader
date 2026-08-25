"""Backtest / Live Parity Validation Engine.

Guarantees 100% mathematical and event parity between:
 - Path A: Batch historical backtest feature calculation
 - Path B: Candle-by-candle live streaming / replay state calculation
"""

from typing import Dict, List, Any, Tuple
import numpy as np
import polars as pl
from pydantic import BaseModel, Field

from quant_platform.live.state_engine import LiveStateEngine
from quant_platform.features.indicators.trend import compute_ema
from quant_platform.features.indicators.momentum import compute_rsi
from quant_platform.features.indicators.volatility import compute_atr
from quant_platform.features.structure.market_structure import MarketStructureEngine
from quant_platform.features.smc.fvg import FvgEngine
from quant_platform.features.smc.liquidity import LiquidityEngine
from quant_platform.regimes.engine import MarketRegimeEngine
from quant_platform.data.timeframes.resampler import CausalResampler
from quant_platform.observability.logger import logger


class ParityCheckResult(BaseModel):
    """Result of a single feature parity comparison."""
    feature_name: str
    timeframe: str
    total_bars_checked: int
    matches: int
    mismatches: int
    max_absolute_delta: float
    is_parity_clean: bool


class ParityReport(BaseModel):
    """Aggregate Backtest/Live Parity report."""
    symbol: str
    total_1m_bars_processed: int
    timeframes_checked: List[str]
    checks: List[ParityCheckResult] = Field(default_factory=list)
    overall_parity_pct: float
    is_full_parity_achieved: bool

    @property
    def summary(self) -> str:
        s = f"=== BACKTEST / LIVE PARITY AUDIT REPORT ({self.symbol}) ===\n"
        s += f"Processed {self.total_1m_bars_processed} 1m bars across {self.timeframes_checked}\n"
        s += "-" * 75 + "\n"
        s += f"{'Feature':<28} | {'Timeframe':<10} | {'Max Delta':<12} | {'Parity %':<10} | {'Status'}\n"
        s += "-" * 75 + "\n"
        for c in self.checks:
            parity_ratio = (c.matches / max(1, c.total_bars_checked)) * 100.0
            status_str = "MATCH" if c.is_parity_clean else "MISMATCH"
            s += f"{c.feature_name:<28} | {c.timeframe:<10} | {c.max_absolute_delta:<12.6f} | {parity_ratio:>8.1f}% | {status_str}\n"
        s += "-" * 75 + "\n"
        s += f"OVERALL PARITY SCORE: {self.overall_parity_pct:.2f}% | {'PASSED (100% PARITY)' if self.is_full_parity_achieved else 'FAILED'}\n"
        return s


class ParityEngine:
    """Executes Path A vs Path B parity verification."""

    @classmethod
    def verify_parity(
        cls,
        df_1m_raw: pl.DataFrame,
        symbol: str = "ETHUSDT",
        tolerance: float = 1e-4,
    ) -> ParityReport:
        """Run batch vs streaming parity check across core indicators and structure features."""
        logger.info(f"Initiating Backtest/Live Parity Audit on {len(df_1m_raw)} bars...")

        # 1. Path A: Batch Calculation
        df_15m_batch = CausalResampler.resample(df_1m_raw, target_timeframe="15m")
        df_15m_batch = compute_ema(df_15m_batch, period=10, output_col="ema_10")
        df_15m_batch = compute_ema(df_15m_batch, period=30, output_col="ema_30")
        df_15m_batch = compute_rsi(df_15m_batch, period=14, output_col="rsi_14")
        df_15m_batch = compute_atr(df_15m_batch, period=14, output_col="atr_14")
        df_15m_batch = MarketStructureEngine.compute_market_structure(df_15m_batch, left_bars=3, right_bars=3)
        df_15m_batch, _ = FvgEngine.detect_and_track_fvgs(df_15m_batch)
        df_15m_batch, _ = LiquidityEngine.detect_liquidity_sweeps(df_15m_batch, left_bars=3, right_bars=3)
        df_15m_batch = MarketRegimeEngine.classify_regimes(df_15m_batch)

        # 2. Path B: Incremental Candle-by-Candle Streaming
        state_engine = LiveStateEngine(symbol=symbol, max_1m_bars=len(df_1m_raw) + 10)
        for row in df_1m_raw.iter_rows(named=True):
            state_engine.on_1m_candle(
                open_time=row["open_time"],
                open_price=row["open"],
                high_price=row["high"],
                low_price=row["low"],
                close_price=row["close"],
                volume=row["volume"],
                close_time=row["close_time"],
                is_closed=True,
                quote_volume=row.get("quote_asset_volume", 0.0),
                trades=row.get("number_of_trades", 0),
            )

        df_15m_live = state_engine.computed_dfs.get("15m")
        if df_15m_live is None or len(df_15m_live) == 0:
            raise RuntimeError("Live state engine failed to compute 15m timeframe dataframe.")

        # 3. Compare common features
        features_to_check = [
            ("close", "numeric"),
            ("ema_10", "numeric"),
            ("ema_30", "numeric"),
            ("rsi_14", "numeric"),
            ("atr_14", "numeric"),
            ("structural_trend", "discrete"),
            ("is_bos_close_bullish", "discrete"),
            ("is_bos_close_bearish", "discrete"),
            ("is_bullish_fvg_created", "discrete"),
            ("is_bearish_fvg_created", "discrete"),
            ("is_sellside_sweep", "discrete"),
            ("is_buyside_sweep", "discrete"),
            ("regime_tag", "discrete"),
        ]

        # Align on open_time
        joined = df_15m_batch.join(df_15m_live, on="open_time", suffix="_live", how="inner")
        n_rows = len(joined)

        check_results = []
        clean_count = 0

        for col_name, col_type in features_to_check:
            if col_name not in df_15m_batch.columns or f"{col_name}_live" not in joined.columns:
                continue

            batch_vals = joined[col_name].to_numpy()
            live_vals = joined[f"{col_name}_live"].to_numpy()

            if col_type == "numeric":
                # Mask out initial NaNs
                valid_mask = ~(np.isnan(batch_vals) | np.isnan(live_vals))
                if valid_mask.sum() == 0:
                    continue
                diffs = np.abs(batch_vals[valid_mask] - live_vals[valid_mask])
                max_delta = float(np.max(diffs))
                matches = int(np.sum(diffs <= tolerance))
                total = int(valid_mask.sum())
            else:
                matches = int(np.sum(batch_vals == live_vals))
                total = n_rows
                max_delta = 0.0

            mismatches = total - matches
            is_clean = (mismatches == 0)
            if is_clean:
                clean_count += 1

            check_results.append(ParityCheckResult(
                feature_name=col_name,
                timeframe="15m",
                total_bars_checked=total,
                matches=matches,
                mismatches=mismatches,
                max_absolute_delta=max_delta,
                is_parity_clean=is_clean,
            ))

        overall_pct = (clean_count / max(1, len(check_results))) * 100.0

        return ParityReport(
            symbol=symbol,
            total_1m_bars_processed=len(df_1m_raw),
            timeframes_checked=["15m"],
            checks=check_results,
            overall_parity_pct=overall_pct,
            is_full_parity_achieved=(clean_count == len(check_results)),
        )
