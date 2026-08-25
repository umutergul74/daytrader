"""Configuration package."""

from quant_platform.config.settings import PlatformSettings, settings
from quant_platform.config.constants import (
    DEFAULT_MARKET_ID,
    DEFAULT_SYMBOL,
    CANONICAL_TIMEFRAME,
    SUPPORTED_TIMEFRAMES,
    DEFAULT_MAKER_FEE_RATE,
    DEFAULT_TAKER_FEE_RATE,
    DEFAULT_SLIPPAGE_BPS,
)

__all__ = [
    "PlatformSettings",
    "settings",
    "DEFAULT_MARKET_ID",
    "DEFAULT_SYMBOL",
    "CANONICAL_TIMEFRAME",
    "SUPPORTED_TIMEFRAMES",
    "DEFAULT_MAKER_FEE_RATE",
    "DEFAULT_TAKER_FEE_RATE",
    "DEFAULT_SLIPPAGE_BPS",
]
