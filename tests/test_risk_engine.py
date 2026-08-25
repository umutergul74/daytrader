"""Tests for Risk Engine and Position Sizing."""

from quant_platform.domain.signal import (
    SignalCandidate,
    SignalDirection,
    SignalType,
    StopCandidate,
    TargetCandidate,
)
from quant_platform.risk.engine import RiskEngine
from quant_platform.risk.sizing import PositionSizer


def test_risk_engine_validates_rr_and_stops():
    """Verify RiskEngine approves valid R:R setups and rejects poor R:R setups."""
    engine = RiskEngine(min_risk_reward=1.5, max_stop_distance_pct=0.05)

    # Valid Signal (Entry 2000, Stop 1950 (-2.5%), Target 2100 (+5.0% -> 2:1 RR))
    valid_sig = SignalCandidate(
        signal_id="SIG-TEST-1",
        strategy_id="test",
        strategy_version="v1",
        timestamp=1000,
        direction=SignalDirection.LONG,
        entry_price=2000.0,
        stop_candidate=StopCandidate(name="SL", price=1950.0, risk_distance=50.0),
        target_candidates=[TargetCandidate(name="TP1", price=2100.0, reward_r=2.0)],
        calculated_rr=2.0,
    )
    decision = engine.evaluate_signal(valid_sig)
    assert decision.is_approved is True
    assert decision.risk_reward_ratio == 2.0

    # Invalid Low RR Signal (Entry 2000, Stop 1950, Target 2025 -> 0.5:1 RR)
    low_rr_sig = valid_sig.model_copy(
        update={"target_candidates": [TargetCandidate(name="TP1", price=2025.0, reward_r=0.5)]}
    )
    decision_bad = engine.evaluate_signal(low_rr_sig)
    assert decision_bad.is_approved is False
    assert "below minimum" in decision_bad.rejection_reason


def test_position_sizing_fixed_risk():
    """Verify position sizer calculates exact risk fraction and checks min notional."""
    sizer = PositionSizer(min_notional=5.0, qty_step=0.001)

    # $10,000 equity, risk 1% = $100. Entry = 2000, Stop = 1950 (risk per unit = $50)
    # Expected qty = 100 / 50 = 2.0 ETH
    res = sizer.size_fixed_risk(equity=10000.0, entry_price=2000.0, stop_price=1950.0, risk_fraction=0.01)
    assert res.is_valid is True
    assert res.quantity == 2.0
    assert res.notional_value == 4000.0
    assert res.risk_amount_usdt == 100.0
