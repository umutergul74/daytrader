"""Tests for Champion / Challenger Coordinator."""

import polars as pl
import pytest
from quant_platform.live.state_engine import LiveStateEngine
from quant_platform.live.champion_challenger import ChampionChallengerCoordinator
from quant_platform.strategies.baselines.breakout import BreakoutSanityStrategy
from quant_platform.strategies.baselines.ema_trend import EmaTrendStrategy


def test_champion_challenger_evaluation(synthetic_1m_data: pl.DataFrame):
    """Verify simultaneous multi-strategy evaluation with isolated paper portfolios."""
    state_engine = LiveStateEngine(symbol="ETHUSDT")

    # Ingest synthetic bars
    for row in synthetic_1m_data.tail(300).iter_rows(named=True):
        state_engine.on_1m_candle(
            open_time=row["open_time"],
            open_price=row["open"],
            high_price=row["high"],
            low_price=row["low"],
            close_price=row["close"],
            volume=row["volume"],
            close_time=row["close_time"],
            is_closed=True,
        )

    champ = BreakoutSanityStrategy(lookback_period=20)
    challengers = {
        "EmaTrend": EmaTrendStrategy(fast_period=10, slow_period=30),
    }

    coord = ChampionChallengerCoordinator(champion_strategy=champ, challengers=challengers, enable_telegram=False)

    opened = coord.evaluate_live_bar(state_engine)
    assert coord.total_bars_evaluated == 1

    table = coord.get_comparative_table()
    assert len(table) == 2
    roles = {r.role for r in table}
    assert "CHAMPION" in roles
    assert "CHALLENGER_A" in roles
