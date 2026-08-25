"""Telegram Live Signal & State Notification Engine.

Formats and delivers institutional-grade real-time shadow alerts with full evidence checkmarks,
risk parameters, market regime context, and safety disclaimers.
"""

from typing import Optional, Dict, Any, List
import urllib.request
import urllib.parse
import json

from quant_platform.config.settings import settings
from quant_platform.domain.trade import TradeDirection
from quant_platform.live.paper_broker import PaperPosition, TradeRecord
from quant_platform.observability.logger import logger


class TelegramSignalFormatter:
    """Formats rich structured Markdown/HTML alerts for Telegram delivery."""

    @staticmethod
    def format_signal_alert(
        strategy_name: str,
        symbol: str,
        direction: TradeDirection,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: Optional[float],
        risk_reward_ratio: float,
        market_regime: str,
        evidence_points: List[str],
        confidence_score: int,
        signal_id: str,
        experiment_evidence: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format an institutional shadow signal alert."""
        icon = "🟢" if direction == TradeDirection.LONG else "🔴"
        action = "LONG" if direction == TradeDirection.LONG else "SHORT"

        msg = f"{icon} <b>{symbol} {action} — SHADOW SIGNAL</b>\n\n"
        msg += f"<b>Strategy:</b> <code>{strategy_name}</code>\n"
        msg += f"<b>Entry:</b> ${entry_price:,.2f}\n"
        msg += f"<b>Stop Loss:</b> ${stop_loss:,.2f}\n"
        msg += f"<b>TP1:</b> ${take_profit_1:,.2f}\n"
        if take_profit_2:
            msg += f"<b>TP2:</b> ${take_profit_2:,.2f}\n"
        msg += f"<b>Risk/Reward:</b> 1 : {risk_reward_ratio:.2f}\n\n"

        msg += f"<b>Market Regime:</b> {market_regime}\n\n"
        msg += "<b>Evidence Checklist:</b>\n"
        for pt in evidence_points:
            msg += f"  ✓ {pt}\n"

        msg += f"\n<b>Confidence Score:</b> {confidence_score}/100\n"

        if experiment_evidence:
            msg += "\n<b>Research Ledger Evidence:</b>\n"
            for k, v in experiment_evidence.items():
                msg += f"  • {k}: {v}\n"

        msg += f"\n<b>Signal ID:</b> <code>{signal_id}</code>\n\n"
        msg += "⚠️ <i>THIS IS A SHADOW/PAPER SIGNAL. NO REAL ORDER HAS BEEN PLACED.</i>"
        return msg

    @staticmethod
    def format_position_closed(trade: TradeRecord) -> str:
        """Format a trade exit / settlement notification."""
        pnl_icon = "💰" if trade.net_pnl > 0 else "🛑"
        msg = f"{pnl_icon} <b>SHADOW POSITION CLOSED: {trade.symbol}</b>\n\n"
        msg += f"<b>Strategy:</b> <code>{trade.strategy_id}</code>\n"
        msg += f"<b>Direction:</b> {trade.direction.value}\n"
        msg += f"<b>Exit Reason:</b> {trade.exit_reason}\n"
        msg += f"<b>Exit Price:</b> ${trade.exit_price:,.2f}\n"
        msg += f"<b>Net PnL:</b> ${trade.net_pnl:+,.2f} ({trade.net_return_pct:+.2f}%)\n"
        msg += f"<b>Realized R:</b> {trade.r_multiple:+.2f}R\n"
        msg += f"<b>Trade ID:</b> <code>{trade.trade_id}</code>\n\n"
        msg += "⚠️ <i>PAPER TRADE SIMULATION ONLY. NO REAL ASSETS WERE USED.</i>"
        return msg


class TelegramNotifier:
    """Dispatches messages to Telegram Bot API with mock fallback."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID

    def send_message(self, text: str) -> bool:
        """Send message via Telegram HTTP API."""
        if not self.bot_token or not self.chat_id:
            logger.info(f"[TELEGRAM MOCK (No Token)] Dispatched Alert:\n{text}")
            return True

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    logger.info("[TELEGRAM] Message delivered successfully.")
                    return True
        except Exception as e:
            logger.error(f"[TELEGRAM ERROR] Failed to deliver alert: {e}")

        return False
