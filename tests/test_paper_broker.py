from quant_platform.domain.trade import TradeDirection, ExitReason
from quant_platform.live.paper_broker import PaperBroker


def test_paper_broker_lifecycle_long_tp():
    """Verify opening, updating, and profitable TP exit of a paper trade."""
    broker = PaperBroker(initial_capital=10000.0)

    # 1. Open Long
    pos = broker.open_paper_trade(
        strategy_id="test_strat",
        symbol="ETHUSDT",
        direction=TradeDirection.LONG,
        price=2000.0,
        stop_loss=1950.0,
        take_profit_1=2100.0,
        risk_fraction=0.01,
        time_ms=1000,
    )

    assert pos is not None
    assert pos.position_id in broker.portfolio.open_positions
    assert broker.portfolio.cash_balance < 10000.0 # Fees paid

    # 2. Update with non-triggering bar
    closed = broker.update_positions_on_candle(high_price=2050.0, low_price=1980.0, close_price=2020.0, time_ms=2000)
    assert len(closed) == 0
    assert len(broker.portfolio.open_positions) == 1

    # 3. Update with TP triggering bar
    closed = broker.update_positions_on_candle(high_price=2110.0, low_price=2010.0, close_price=2090.0, time_ms=3000)
    assert len(closed) == 1
    trade = closed[0]
    assert trade.exit_reason == ExitReason.TAKE_PROFIT
    assert trade.net_pnl > 0
    assert len(broker.portfolio.open_positions) == 0
    assert broker.portfolio.total_trades_count == 1
    assert broker.portfolio.profitable_trades_count == 1


def test_paper_broker_lifecycle_short_sl():
    """Verify opening and stop loss exit of a short paper trade."""
    broker = PaperBroker(initial_capital=10000.0)

    # Open Short
    pos = broker.open_paper_trade(
        strategy_id="test_strat",
        symbol="ETHUSDT",
        direction=TradeDirection.SHORT,
        price=2000.0,
        stop_loss=2050.0,
        take_profit_1=1900.0,
        risk_fraction=0.01,
        time_ms=1000,
    )

    assert pos is not None

    # Update with SL triggering bar
    closed = broker.update_positions_on_candle(high_price=2060.0, low_price=1990.0, close_price=2055.0, time_ms=2000)
    assert len(closed) == 1
    trade = closed[0]
    assert trade.exit_reason == ExitReason.STOP_LOSS
    assert trade.net_pnl < 0
