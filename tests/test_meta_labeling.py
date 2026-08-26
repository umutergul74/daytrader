"""Tests for Meta-Labeling Dataset Builder."""

import polars as pl
from quant_platform.domain.signal import SignalCandidate, StopCandidate, TargetCandidate
from quant_platform.domain.trade import TradeDirection
from quant_platform.ml.meta_labeling import MetaLabelingEngine


def test_meta_labeling_triple_barrier():
    """Verify triple-barrier labeling on candidate signals."""
    df_15m = pl.DataFrame({
        "open_time": [1000, 2000, 3000, 4000, 5000],
        "close_time": [1999, 2999, 3999, 4999, 5999],
        "open": [2000.0, 2005.0, 2015.0, 2025.0, 2030.0],
        "high": [2005.0, 2020.0, 2030.0, 2040.0, 2050.0], # Hits 2040 TP on bar 4
        "low": [1995.0, 2000.0, 2010.0, 2020.0, 2025.0],  # Does not hit 1980 SL
        "close": [2005.0, 2015.0, 2025.0, 2035.0, 2045.0],
        "volume": [100.0, 100.0, 100.0, 100.0, 100.0],
        "atr_14": [10.0, 10.0, 10.0, 10.0, 10.0],
    })

    cand = SignalCandidate(
        signal_id="SIG-1",
        strategy_id="test_strat",
        strategy_version="v1",
        symbol="ETHUSDT",
        timestamp=1999,
        direction=TradeDirection.LONG,
        entry_price=2000.0,
        stop_candidate=StopCandidate(name="STRUCTURAL", price=1980.0, risk_distance=20.0),
        target_candidates=[TargetCandidate(name="TP1", price=2040.0, reward_r=2.0)],
        calculated_rr=2.0,
    )

    dataset = MetaLabelingEngine.compute_triple_barrier_labels(df_15m, [cand], max_holding_bars=10)
    assert len(dataset.y) == 1
    assert dataset.y[0] == 1 # TP reached first
