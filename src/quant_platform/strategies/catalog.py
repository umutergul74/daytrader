"""Strategy Catalog and Lifecycle Registry."""

from typing import Dict, List, Optional
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy
from quant_platform.strategies.baselines.rsi_reversion import RsiMeanReversionStrategy
from quant_platform.strategies.baselines.breakout import BreakoutSanityStrategy
from quant_platform.strategies.baselines.random_baseline import RandomSanityBaseline
from quant_platform.strategies.advanced.structure_continuation import StructureContinuationStrategy
from quant_platform.strategies.advanced.liquidity_sweep_reversal import LiquiditySweepReversalStrategy
from quant_platform.strategies.advanced.liquidity_sweep_fvg import LiquiditySweepFVGStrategy
from quant_platform.strategies.advanced.fvg_continuation import FvgTrendContinuationStrategy
from quant_platform.strategies.advanced.regime_mean_reversion import RegimeAwareMeanReversionStrategy
from quant_platform.strategies.advanced.session_institutional_smc import SessionInstitutionalSMCStrategy
from quant_platform.strategies.advanced.institutional_macro_champion import InstitutionalMacroStructureChampion
from quant_platform.strategies.advanced.institutional_smart_money_confluence import InstitutionalSmartMoneyConfluenceStrategy


class StrategyCatalog:
    """Registry of benchmark baseline and advanced research strategies."""

    _strategies: Dict[str, StrategyMetadata] = {}
    _classes: Dict[str, type] = {
        "ema_trend": EmaTrendStrategy,
        "rsi_reversion": RsiMeanReversionStrategy,
        "breakout": BreakoutSanityStrategy,
        "random_baseline": RandomSanityBaseline,
        "structure_continuation": StructureContinuationStrategy,
        "liquidity_sweep_reversal": LiquiditySweepReversalStrategy,
        "liquidity_sweep_fvg": LiquiditySweepFVGStrategy,
        "fvg_continuation": FvgTrendContinuationStrategy,
        "regime_mean_reversion": RegimeAwareMeanReversionStrategy,
        "session_institutional_smc": SessionInstitutionalSMCStrategy,
        "institutional_macro_champion": InstitutionalMacroStructureChampion,
        "institutional_smc_confluence": InstitutionalSmartMoneyConfluenceStrategy,
    }

    @classmethod
    def register(cls, metadata: StrategyMetadata) -> None:
        key = f"{metadata.strategy_id}:{metadata.version}"
        cls._strategies[key] = metadata

    @classmethod
    def get(cls, strategy_id: str, version: str = "v1") -> Optional[StrategyMetadata]:
        return cls._strategies.get(f"{strategy_id}:{version}")

    @classmethod
    def get_strategy_class(cls, name: str) -> Optional[type]:
        return cls._classes.get(name)

    @classmethod
    def list_strategies(cls) -> List[str]:
        return list(cls._classes.keys())

    @classmethod
    def list_all(cls) -> List[StrategyMetadata]:
        return list(cls._strategies.values())

    @classmethod
    def list_by_family(cls, family: str) -> List[StrategyMetadata]:
        return [s for s in cls._strategies.values() if s.family == family]


# Register all strategies
StrategyCatalog.register(EmaTrendStrategy().metadata)
StrategyCatalog.register(RsiMeanReversionStrategy().metadata)
StrategyCatalog.register(BreakoutSanityStrategy().metadata)
StrategyCatalog.register(RandomSanityBaseline().metadata)
StrategyCatalog.register(StructureContinuationStrategy().metadata)
StrategyCatalog.register(LiquiditySweepReversalStrategy().metadata)
StrategyCatalog.register(LiquiditySweepFVGStrategy().metadata)
StrategyCatalog.register(FvgTrendContinuationStrategy().metadata)
StrategyCatalog.register(RegimeAwareMeanReversionStrategy().metadata)
StrategyCatalog.register(SessionInstitutionalSMCStrategy().metadata)
StrategyCatalog.register(InstitutionalMacroStructureChampion().metadata)
StrategyCatalog.register(InstitutionalSmartMoneyConfluenceStrategy().metadata)
