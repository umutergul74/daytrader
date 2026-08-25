"""Research experiment domain models."""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ExperimentStatus(str, Enum):
    PROPOSED = "proposed"
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    SHADOW = "shadow"
    DEPRECATED = "deprecated"
    INVALID_DUE_TO_LEAKAGE = "invalid_due_to_leakage"
    INVALID_DUE_TO_DATA = "invalid_due_to_data"
    INVALID_DUE_TO_EXECUTION = "invalid_due_to_execution_assumption"


class QuantMetrics(BaseModel):
    """Calculated quant performance metrics."""
    total_net_return: float
    gross_return: float
    total_fees: float
    total_slippage: float
    total_funding: float
    trade_count: int
    win_rate: float
    average_winner: float
    average_loser: float
    payoff_ratio: float
    expectancy: float
    average_r: float
    median_r: float
    profit_factor: float
    max_drawdown_pct: float
    max_drawdown_duration_bars: int
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    exposure_pct: float
    long_trades: int
    short_trades: int
    long_win_rate: float
    short_win_rate: float
    consecutive_wins_max: int
    consecutive_losses_max: int
    intrabar_ambiguity_count: int = 0


class ExperimentRecord(BaseModel):
    """Complete, immutable audit record of a research experiment."""
    experiment_id: str = Field(description="Unique experiment ID (e.g. EXP-20260824-233100-a72bf9)")
    hypothesis: str
    experiment_type: str = "BACKTEST"
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    strategy_id: str
    strategy_version: str
    feature_set_version: str
    parameters: Dict[str, Any]
    parameter_hash: str
    dataset_fingerprint: str
    symbol: str = "ETHUSDT"
    timeframe: str = "1m"
    date_range_start: str
    date_range_end: str
    train_range: Optional[tuple[str, str]] = None
    validation_range: Optional[tuple[str, str]] = None
    test_range: Optional[tuple[str, str]] = None
    git_sha: str = "unknown"
    git_dirty: bool = False
    random_seed: int = 42
    cost_model: Dict[str, Any]
    execution_model: str
    risk_model: str
    metrics: Optional[QuantMetrics] = None
    trade_count: int = 0
    regime_metrics: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    conclusion: Optional[str] = None
    lessons_learned: Optional[str] = None
    rejection_reason: Optional[str] = None
    recommended_next_experiment: Optional[str] = None
    parent_experiment_id: Optional[str] = None
