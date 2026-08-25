"""Risk Evaluation Engine."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from quant_platform.domain.signal import SignalCandidate, SignalDirection, SignalType
from quant_platform.observability.logger import logger


class RiskDecision(BaseModel):
    is_approved: bool
    signal_candidate: SignalCandidate
    rejection_reason: Optional[str] = None
    adjusted_stop_price: Optional[float] = None
    adjusted_target_price: Optional[float] = None
    risk_reward_ratio: float = 0.0
    risk_notes: Dict[str, Any] = Field(default_factory=dict)


class RiskEngine:
    """Evaluates alpha signals against independent risk gates."""

    def __init__(
        self,
        min_risk_reward: float = 1.5,
        max_stop_distance_pct: float = 0.08,  # 8% max stop distance
        min_stop_distance_pct: float = 0.001, # 0.1% min stop distance
        max_holding_bars: int = 240,         # 4 hours on 1m bars
    ):
        self.min_risk_reward = min_risk_reward
        self.max_stop_distance_pct = max_stop_distance_pct
        self.min_stop_distance_pct = min_stop_distance_pct
        self.max_holding_bars = max_holding_bars

    def evaluate_signal(self, signal: SignalCandidate) -> RiskDecision:
        """Evaluate signal against strict structural and risk rules."""
        if signal.direction == SignalDirection.NO_TRADE:
            return RiskDecision(
                is_approved=False,
                signal_candidate=signal,
                rejection_reason="Strategy emitted NO_TRADE",
            )

        if not signal.stop_candidate:
            return RiskDecision(
                is_approved=False,
                signal_candidate=signal,
                rejection_reason="No structural stop loss provided",
            )

        entry_price = signal.entry_price
        stop_price = signal.stop_candidate.price

        # Check stop distance
        stop_dist = abs(entry_price - stop_price)
        stop_pct = stop_dist / entry_price

        if stop_pct < self.min_stop_distance_pct:
            return RiskDecision(
                is_approved=False,
                signal_candidate=signal,
                rejection_reason=f"Stop distance {round(stop_pct*100, 3)}% below minimum {round(self.min_stop_distance_pct*100, 3)}%",
            )

        if stop_pct > self.max_stop_distance_pct:
            return RiskDecision(
                is_approved=False,
                signal_candidate=signal,
                rejection_reason=f"Stop distance {round(stop_pct*100, 3)}% exceeds maximum {round(self.max_stop_distance_pct*100, 3)}%",
            )

        # Check direction validity vs stop
        if signal.direction == SignalDirection.LONG and stop_price >= entry_price:
            return RiskDecision(
                is_approved=False,
                signal_candidate=signal,
                rejection_reason=f"Invalid LONG stop price {stop_price} >= entry {entry_price}",
            )
        if signal.direction == SignalDirection.SHORT and stop_price <= entry_price:
            return RiskDecision(
                is_approved=False,
                signal_candidate=signal,
                rejection_reason=f"Invalid SHORT stop price {stop_price} <= entry {entry_price}",
            )

        # Check target candidates and R:R
        if not signal.target_candidates:
            return RiskDecision(
                is_approved=False,
                signal_candidate=signal,
                rejection_reason="No target candidates provided",
            )

        tp1 = signal.target_candidates[0]
        tp_dist = abs(tp1.price - entry_price)
        actual_rr = tp_dist / stop_dist

        if actual_rr < self.min_risk_reward:
            return RiskDecision(
                is_approved=False,
                signal_candidate=signal,
                rejection_reason=f"Reward-to-risk {round(actual_rr, 2)} is below minimum {self.min_risk_reward}",
                risk_reward_ratio=actual_rr,
            )

        return RiskDecision(
            is_approved=True,
            signal_candidate=signal,
            adjusted_stop_price=stop_price,
            adjusted_target_price=tp1.price,
            risk_reward_ratio=actual_rr,
            risk_notes={"stop_pct": stop_pct, "max_holding_bars": self.max_holding_bars},
        )
