"""Binance USD(S)-M Futures Microstructure Data Providers.

Acquires and generates synthetic/historical Aggregate Trades, Open Interest, and Liquidation datasets.
"""

from typing import Optional, List, Dict, Any
import numpy as np
import polars as pl

from quant_platform.domain.events import (
    AggTradeEvent,
    OpenInterestEvent,
    LiquidationEvent,
    AGG_TRADE_SCHEMA,
    OPEN_INTEREST_SCHEMA,
    LIQUIDATION_SCHEMA,
)
from quant_platform.observability.logger import logger


class BinanceAggTradesProvider:
    """Acquires and normalizes Binance USD(S)-M Futures aggTrades."""

    @staticmethod
    def generate_synthetic_agg_trades(
        df_1m: pl.DataFrame,
        trades_per_bar: int = 10,
        random_seed: int = 42,
    ) -> pl.DataFrame:
        """Generates realistic synthetic aggTrades aligned with 1m OHLCV bars for testing."""
        np.random.seed(random_seed)
        rows: List[Dict[str, Any]] = []
        trade_counter = 1000000

        for row in df_1m.iter_rows(named=True):
            open_t = row["open_time"]
            close_t = row["close_time"]
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            vol = row["volume"]
            vol_per_trade = vol / max(1, trades_per_bar)

            times = np.linspace(open_t, close_t - 100, trades_per_bar, dtype=np.int64)
            prices = np.linspace(o, c, trades_per_bar) + np.random.uniform(-0.5, 0.5, trades_per_bar)
            prices[0] = o
            prices[-1] = c
            prices = np.clip(prices, l, h)

            for t_ms, p_val in zip(times, prices):
                trade_counter += 1
                is_buyer_maker = bool(np.random.rand() > 0.52)
                rows.append({
                    "trade_id": trade_counter,
                    "price": float(p_val),
                    "quantity": float(vol_per_trade * np.random.uniform(0.5, 1.5)),
                    "is_buyer_maker": is_buyer_maker,
                    "event_time_ms": int(t_ms),
                    "received_at_ms": int(t_ms + np.random.randint(10, 50)),
                })

        df = pl.DataFrame(rows, schema=AGG_TRADE_SCHEMA)
        logger.info(f"Generated {len(df):,} synthetic aggTrades across {len(df_1m)} 1m bars.")
        return df


class BinanceMicrostructureProvider:
    """Acquires and generates Open Interest and Liquidation event datasets."""

    @staticmethod
    def generate_synthetic_open_interest(
        df_1m: pl.DataFrame,
        base_oi: float = 500000.0,
        random_seed: int = 42,
    ) -> pl.DataFrame:
        """Generates synthetic 5m Open Interest series aligned with klines."""
        np.random.seed(random_seed)
        rows: List[Dict[str, Any]] = []

        curr_oi = base_oi
        df_5m = df_1m.filter(pl.col("open_time") % 300_000 == 0)

        for row in df_5m.iter_rows(named=True):
            t_ms = row["open_time"]
            price = row["close"]
            delta_oi = np.random.normal(0, 1500.0)
            curr_oi = max(100000.0, curr_oi + delta_oi)
            notional_oi = curr_oi * price

            rows.append({
                "open_interest": float(curr_oi),
                "open_interest_usdt": float(notional_oi),
                "event_time_ms": int(t_ms),
                "received_at_ms": int(t_ms + 25),
            })

        df = pl.DataFrame(rows, schema=OPEN_INTEREST_SCHEMA)
        logger.info(f"Generated {len(df):,} synthetic Open Interest snapshots.")
        return df

    @staticmethod
    def generate_synthetic_liquidations(
        df_1m: pl.DataFrame,
        burst_probability: float = 0.05,
        random_seed: int = 42,
    ) -> pl.DataFrame:
        """Generates synthetic forced liquidation events occurring on high volatility bars."""
        np.random.seed(random_seed)
        rows: List[Dict[str, Any]] = []
        liq_counter = 500000

        for row in df_1m.iter_rows(named=True):
            t_ms = row["open_time"]
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            bar_range = h - l

            if np.random.rand() < burst_probability or bar_range > 15.0:
                is_long_liq = (c < o)
                liq_side = "SELL" if is_long_liq else "BUY"
                liq_counter += 1
                liq_price = l if is_long_liq else h
                liq_qty = float(np.random.exponential(scale=25.0) + 5.0)

                rows.append({
                    "order_id": f"LIQ-{liq_counter}",
                    "side": liq_side,
                    "price": float(liq_price),
                    "quantity": float(liq_qty),
                    "event_time_ms": int(t_ms + np.random.randint(500, 50000)),
                    "received_at_ms": int(t_ms + 50050),
                })

        df = pl.DataFrame(rows, schema=LIQUIDATION_SCHEMA)
        logger.info(f"Generated {len(df):,} synthetic liquidation events.")
        return df
