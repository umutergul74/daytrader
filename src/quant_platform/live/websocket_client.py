"""Binance USD(S)-M Futures WebSocket Stream Client.

Streams live 1m klines, mark price, and funding rate updates from Binance USD(S)-M Futures,
dispatching closed candles to the Live State Engine and Champion/Challenger Coordinator.
"""

import asyncio
import json
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timezone
import urllib.request

from quant_platform.live.state_engine import LiveStateEngine
from quant_platform.live.champion_challenger import ChampionChallengerCoordinator
from quant_platform.observability.logger import logger


class BinanceFuturesWebSocketClient:
    """Async WebSocket client for Binance USD(S)-M Futures streams."""

    WS_URL = "wss://fstream.binance.com/ws/{symbol}@kline_1m"

    def __init__(
        self,
        symbol: str = "ETHUSDT",
        state_engine: Optional[LiveStateEngine] = None,
        coordinator: Optional[ChampionChallengerCoordinator] = None,
    ):
        self.symbol = symbol.lower()
        self.state_engine = state_engine or LiveStateEngine(symbol=symbol.upper())
        self.coordinator = coordinator
        self.is_running = False
        self.reconnect_delay_seconds = 2.0
        self.total_messages_received = 0
        self.last_heartbeat_ts: float = 0.0

    async def connect_and_listen(self, max_duration_seconds: Optional[int] = None) -> None:
        """Connect to Binance WebSocket and listen for kline events."""
        try:
            import websockets
        except ImportError:
            logger.error("`websockets` package not installed. Run `pip install websockets` or use market replay mode.")
            return

        url = self.WS_URL.format(symbol=self.symbol)
        self.is_running = True
        t_start = time.time()

        logger.info(f"Connecting to Binance USD(S)-M Futures WebSocket: {url}")

        while self.is_running:
            if max_duration_seconds and (time.time() - t_start) >= max_duration_seconds:
                logger.info(f"Session reached max duration ({max_duration_seconds}s). Stopping.")
                break

            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info(f"Connected to {self.symbol.upper()} 1m WebSocket stream.")
                    self.reconnect_delay_seconds = 2.0

                    async for message in ws:
                        self.total_messages_received += 1
                        self.last_heartbeat_ts = time.time()
                        self._process_message(message)

                        if max_duration_seconds and (time.time() - t_start) >= max_duration_seconds:
                            break

            except Exception as e:
                logger.warning(f"WebSocket connection dropped: {e}. Reconnecting in {self.reconnect_delay_seconds}s...")
                await asyncio.sleep(self.reconnect_delay_seconds)
                self.reconnect_delay_seconds = min(30.0, self.reconnect_delay_seconds * 1.5)

    def _process_message(self, raw_msg: str) -> None:
        """Parse Binance kline payload and trigger state evaluation."""
        try:
            data = json.loads(raw_msg)
            if "k" not in data:
                return

            k = data["k"]
            open_time = int(k["t"])
            close_time = int(k["T"])
            open_price = float(k["o"])
            high_price = float(k["h"])
            low_price = float(k["l"])
            close_price = float(k["c"])
            volume = float(k["v"])
            quote_volume = float(k["q"])
            trades = int(k["n"])
            is_closed = bool(k["x"])

            triggered = self.state_engine.on_1m_candle(
                open_time=open_time,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                close_time=close_time,
                is_closed=is_closed,
                quote_volume=quote_volume,
                trades=trades,
            )

            # If candle finalized, evaluate Champion/Challenger slots
            if triggered and self.coordinator:
                self.coordinator.evaluate_live_bar(self.state_engine)

        except Exception as e:
            logger.error(f"Error parsing kline event: {e}")

    def stop(self) -> None:
        """Stop listening to WebSocket stream."""
        self.is_running = False
