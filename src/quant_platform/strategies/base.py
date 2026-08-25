"""Base Strategy Protocol."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import polars as pl

from quant_platform.domain.signal import SignalCandidate


class StrategyMetadata(BaseModel):
    strategy_id: str
    version: str = "v1"
    hypothesis: str
    required_features: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    supported_regimes: List[str] = Field(default_factory=lambda: ["ALL"])
    author: str = "Quant Research Team"


class BaseStrategy(ABC):
    """Abstract base strategy."""

    def __init__(self, metadata: StrategyMetadata):
        self.metadata = metadata

    @abstractmethod
    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        """Generate structured SignalCandidates from causal DataFrame."""
        pass
