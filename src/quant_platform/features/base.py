"""Base feature definitions and metadata."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import polars as pl


class FeatureMetadata(BaseModel):
    """Machine-readable metadata for quantitative features."""
    feature_id: str
    version: str = "v1"
    category: str
    name: str
    description: str
    required_columns: List[str] = Field(default_factory=lambda: ["open", "high", "low", "close", "volume"])
    parameters: Dict[str, Any] = Field(default_factory=dict)
    lookback_bars: int
    causality_status: str = "strictly_causal"  # strictly_causal, confirmed_delay, lookahead_risk


class BaseFeature(ABC):
    """Abstract base class for all feature calculations."""

    def __init__(self, metadata: FeatureMetadata):
        self.metadata = metadata

    @abstractmethod
    def compute(self, df: pl.DataFrame) -> pl.DataFrame:
        """Compute feature columns and return DataFrame with added columns."""
        pass
