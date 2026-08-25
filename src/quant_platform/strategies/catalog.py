"""Strategy Catalog for strategy registration and lookup."""

from typing import Dict, List, Optional, Type
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.strategies.baselines.rsi_reversion import RsiMeanReversionStrategy
from quant_platform.strategies.baselines.breakout import BreakoutSanityStrategy
from quant_platform.strategies.baselines.random_baseline import RandomSanityBaseline


class StrategyCatalog:
    """Registry of implemented trading strategies."""

    _registry: Dict[str, Type[BaseStrategy]] = {
        "ema_trend": EmaTrendStrategy,
        "rsi_reversion": RsiMeanReversionStrategy,
        "breakout": BreakoutSanityStrategy,
        "random_baseline": RandomSanityBaseline,
    }

    @classmethod
    def get_strategy_class(cls, name: str) -> Optional[Type[BaseStrategy]]:
        return cls._registry.get(name.lower())

    @classmethod
    def list_strategies(cls) -> List[str]:
        return list(cls._registry.keys())
