"""Timeframe definitions and conversion utilities."""

from enum import Enum
from typing import Dict


class Timeframe(str, Enum):
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    H6 = "6h"
    H12 = "12h"
    D1 = "1d"
    W1 = "1w"

    @property
    def minutes(self) -> int:
        mapping: Dict[str, int] = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "6h": 360,
            "12h": 720,
            "1d": 1440,
            "1w": 10080,
        }
        return mapping[self.value]

    @property
    def milliseconds(self) -> int:
        return self.minutes * 60 * 1000

    @property
    def polars_rule(self) -> str:
        """Polars dynamic groupby/resample duration rule."""
        if self.value.endswith("m"):
            return f"{self.minutes}m"
        elif self.value.endswith("h"):
            return f"{self.minutes // 60}h"
        elif self.value.endswith("d"):
            return f"{self.minutes // 1440}d"
        elif self.value.endswith("w"):
            return "1w"
        return "1m"
