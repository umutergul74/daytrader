"""Champion / Challenger Multi-Strategy Coordinator.

Runs Champion alongside multiple Challenger strategies on the same live streaming market feed,
maintaining isolated paper portfolios and comparative performance tracking.
"""

from typing import Dict, List, Optional, Any, Tuple
import polars as pl
from pydantic import BaseModel, Field

from quant_platform.strategies.base import BaseStrategy
from quant_platform.live.state_engine import LiveStateEngine
from quant_platform.live.paper_broker import PaperBroker, PaperPosition, TradeRecord
from quant_platform.live.decision_logger import DecisionLogger
from quant_platform.live.drift_monitor import DriftMonitor, DriftStatus
from quant_platform.notifications.telegram_bot import TelegramNotifier, TelegramSignalFormatter
from quant_platform.domain.trade import TradeDirection
from quant_platform.observability.logger import logger


class StrategyExecutionSlot:
    """Execution container for a strategy in the live pipeline."""
    def __init__(
        self,
        name: str,
        role: str, # CHAMPION, CHALLENGER_A, CHALLENGER_B, etc.
        strategy: BaseStrategy,
        initial_capital: float = 10000.0,
        enable_telegram: bool = True,
    ):
        self.name = name
        self.role = role
        self.strategy = strategy
        self.broker = PaperBroker(portfolio_name=f"{role}_{name}", initial_capital=initial_capital)
        self.drift_monitor = DriftMonitor(strategy_id=strategy.metadata.strategy_id)
        self.enable_telegram = enable_telegram


class ComparativeMetrics(BaseModel):
    """Comparative performance row for Champion vs Challengers."""
    role: str
    strategy_name: str
    total_trades: int
    net_pnl_usdt: float
    net_return_pct: float
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    open_positions_count: int


class ChampionChallengerCoordinator:
    """Coordinates concurrent evaluation of Champion and Challenger strategies."""

    def __init__(
        self,
        champion_strategy: BaseStrategy,
        challengers: Optional[Dict[str, BaseStrategy]] = None,
        initial_capital_per_slot: float = 10000.0,
        enable_telegram: bool = True,
    ):
        self.slots: Dict[str, StrategyExecutionSlot] = {}

        # 1. Champion Slot
        self.champion_slot = StrategyExecutionSlot(
            name=champion_strategy.metadata.strategy_id,
            role="CHAMPION",
            strategy=champion_strategy,
            initial_capital=initial_capital_per_slot,
            enable_telegram=enable_telegram,
        )
        self.slots["CHAMPION"] = self.champion_slot

        # 2. Challenger Slots
        if challengers:
            for i, (c_name, c_strat) in enumerate(challengers.items(), start=1):
                slot_key = f"CHALLENGER_{chr(64 + i)}" # CHALLENGER_A, CHALLENGER_B
                self.slots[slot_key] = StrategyExecutionSlot(
                    name=c_strat.metadata.strategy_id,
                    role=slot_key,
                    strategy=c_strat,
                    initial_capital=initial_capital_per_slot,
                    enable_telegram=False, # Challengers execute silently in paper mode
                )

        self.decision_logger = DecisionLogger()
        self.telegram = TelegramNotifier()
        self.total_bars_evaluated: int = 0
        self.signals_generated_count: int = 0

    def evaluate_live_bar(self, state_engine: LiveStateEngine) -> List[PaperPosition]:
        """Called upon each finalized 1m candle close to evaluate all strategy slots."""
        self.total_bars_evaluated += 1
        opened_positions: List[PaperPosition] = []

        snap = state_engine.get_latest_snapshot()
        symbol = snap["symbol"]
        current_price = snap["live_price"]
        current_time_ms = snap["last_finalized_1m"]
        market_regime = snap["regime"]
        struct_trend = 1 if snap["structure_15m"] == "BULLISH" else (-1 if snap["structure_15m"] == "BEARISH" else 0)

        # Update paper broker positions for all slots (SL / TP checks)
        for slot_key, slot in self.slots.items():
            closed_trades = slot.broker.update_positions_on_candle(
                high_price=current_price,
                low_price=current_price,
                close_price=current_price,
                time_ms=current_time_ms,
            )
            for t in closed_trades:
                if slot.enable_telegram:
                    msg = TelegramSignalFormatter.format_position_closed(t)
                    self.telegram.send_message(msg)

        # Evaluate each strategy on its primary execution timeframe (e.g. 15m)
        df_15m = state_engine.computed_dfs.get("15m")
        if df_15m is None or len(df_15m) < 15:
            return opened_positions

        for slot_key, slot in self.slots.items():
            strategy = slot.strategy
            strat_id = strategy.metadata.strategy_id

            # If slot already has max open positions, log and continue
            if len(slot.broker.portfolio.open_positions) >= 1:
                self.decision_logger.log_decision(
                    timestamp_ms=current_time_ms,
                    symbol=symbol,
                    strategy_id=strat_id,
                    action="NO_TRADE",
                    reason="ACTIVE_POSITION_EXISTS",
                    market_regime=market_regime,
                    current_price=current_price,
                    structural_trend=struct_trend,
                )
                slot.drift_monitor.record_bar_evaluation(is_signal_triggered=False)
                continue

            # Run strategy signal generation
            candidate = strategy.generate_latest_signal(df_15m)

            if not candidate or candidate.direction.value not in ["LONG", "SHORT"]:
                self.decision_logger.log_decision(
                    timestamp_ms=current_time_ms,
                    symbol=symbol,
                    strategy_id=strat_id,
                    action="NO_TRADE",
                    reason="NO_STRUCTURAL_SETUP_CONDITIONS",
                    market_regime=market_regime,
                    current_price=current_price,
                    structural_trend=struct_trend,
                )
                slot.drift_monitor.record_bar_evaluation(is_signal_triggered=False)
                continue

            # Resolve stop loss and targets
            stop_price = candidate.stop_candidate.price if candidate.stop_candidate else (current_price * 0.98 if candidate.direction.value == "LONG" else current_price * 1.02)
            tp1_price = candidate.target_candidates[0].price if candidate.target_candidates else (current_price * 1.04 if candidate.direction.value == "LONG" else current_price * 0.96)
            tp2_price = candidate.target_candidates[1].price if len(candidate.target_candidates) > 1 else None

            stop_dist = abs(candidate.entry_price - stop_price)
            tp_dist = abs(tp1_price - candidate.entry_price)
            rr = (tp_dist / max(0.01, stop_dist))

            if rr < 1.5:
                self.decision_logger.log_decision(
                    timestamp_ms=current_time_ms,
                    symbol=symbol,
                    strategy_id=strat_id,
                    action="NO_TRADE",
                    reason=f"INSUFFICIENT_RR ({rr:.2f} < 1.5)",
                    market_regime=market_regime,
                    current_price=current_price,
                    structural_trend=struct_trend,
                )
                slot.drift_monitor.record_bar_evaluation(is_signal_triggered=False)
                continue

            trade_dir = TradeDirection.LONG if candidate.direction.value == "LONG" else TradeDirection.SHORT

            # Valid Trade Candidate!
            pos = slot.broker.open_paper_trade(
                strategy_id=strat_id,
                symbol=symbol,
                direction=trade_dir,
                price=candidate.entry_price,
                stop_loss=stop_price,
                take_profit_1=tp1_price,
                take_profit_2=tp2_price,
                risk_fraction=0.01,
                time_ms=current_time_ms,
            )

            if pos:
                opened_positions.append(pos)
                self.signals_generated_count += 1
                slot.drift_monitor.record_bar_evaluation(is_signal_triggered=True)

                self.decision_logger.log_decision(
                    timestamp_ms=current_time_ms,
                    symbol=symbol,
                    strategy_id=strat_id,
                    action=trade_dir.value,
                    reason="SIGNAL_TRIGGERED",
                    market_regime=market_regime,
                    current_price=current_price,
                    structural_trend=struct_trend,
                    details={"position_id": pos.position_id, "rr": rr},
                )

                # Send Telegram notification if enabled for slot
                if slot.enable_telegram:
                    evidence_pts = candidate.evidence or [
                        f"1H Structural Trend: {snap['structure_1h']}",
                        f"15M Structural Trend: {snap['structure_15m']}",
                        f"Market Regime: {market_regime}",
                        f"Risk-Reward Ratio: 1 : {rr:.2f}",
                    ]
                    msg = TelegramSignalFormatter.format_signal_alert(
                        strategy_name=strat_id,
                        symbol=symbol,
                        direction=trade_dir,
                        entry_price=pos.entry_price,
                        stop_loss=pos.stop_loss,
                        take_profit_1=pos.take_profit_1,
                        take_profit_2=pos.take_profit_2,
                        risk_reward_ratio=rr,
                        market_regime=market_regime,
                        evidence_points=evidence_pts,
                        confidence_score=80,
                        signal_id=pos.position_id,
                    )
                    self.telegram.send_message(msg)

        return opened_positions

    def get_comparative_table(self) -> List[ComparativeMetrics]:
        """Return metrics across Champion and all Challengers."""
        rows = []
        for slot_key, slot in self.slots.items():
            port = slot.broker.portfolio
            wr = (port.profitable_trades_count / max(1, port.total_trades_count)) * 100.0
            
            gross_win = sum(t.net_pnl for t in port.closed_trades if t.net_pnl > 0)
            gross_loss = abs(sum(t.net_pnl for t in port.closed_trades if t.net_pnl < 0))
            pf = (gross_win / max(0.01, gross_loss)) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0)

            rows.append(ComparativeMetrics(
                role=slot.role,
                strategy_name=slot.name,
                total_trades=port.total_trades_count,
                net_pnl_usdt=port.total_net_pnl,
                net_return_pct=(port.total_net_pnl / port.initial_capital) * 100.0,
                win_rate_pct=wr,
                profit_factor=pf,
                max_drawdown_pct=port.max_drawdown_pct,
                open_positions_count=len(port.open_positions),
            ))
        return rows
