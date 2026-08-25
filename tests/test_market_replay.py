"""Tests for Historical Market Replay Engine."""

import polars as pl
import pytest
from quant_platform.live.state_engine import LiveStateEngine
from quant_platform.live.replay import MarketReplayEngine


def test_market_replay_execution(synthetic_1m_data: pl.DataFrame):
    """Verify accelerated market replay feeds every candle and computes state."""
    df_slice = synthetic_1m_data.tail(300)
    state_engine = LiveStateEngine(symbol="ETHUSDT")
    replay_engine = MarketReplayEngine(state_engine=state_engine, speed_multiplier=0.0)

    callbacks_fired = []
    res = replay_engine.replay(df_slice, on_bar_callback=lambda snap: callbacks_fired.append(snap))

    assert res.total_bars_replayed == len(df_slice)
    assert res.duration_seconds >= 0.0
    assert len(callbacks_fired) == len(df_slice)
    assert state_engine.current_live_price == df_slice["close"][-1]
