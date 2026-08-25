"""Strategies package exports."""

from quant_platform.strategies.base import BaseStrategy, StrategyMetadata
from quant_platform.strategies.catalog import StrategyCatalog
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.strategies.baselines.rsi_reversion import RsiMeanReversionStrategy
from quant_platform.strategies.baselines.breakout import BreakoutSanityStrategy
from quant_platform.strategies.baselines.random_baseline import RandomSanityBaseline

__all__ = [
    "BaseStrategy",
    "StrategyMetadata",
    "StrategyCatalog",
    "EmaTrendStrategy",
    "RsiMeanReversionStrategy",
    "BreakoutSanityStrategy",
    "RandomSanityBaseline",
]
