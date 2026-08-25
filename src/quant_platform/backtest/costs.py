"""Trading cost and slippage models."""

from pydantic import BaseModel, Field
from quant_platform.config.constants import (
    DEFAULT_MAKER_FEE_RATE,
    DEFAULT_TAKER_FEE_RATE,
    DEFAULT_SLIPPAGE_BPS,
)


class CostModel(BaseModel):
    """Configurable transaction cost, fee schedule, and slippage model."""
    maker_fee_rate: float = Field(default=DEFAULT_MAKER_FEE_RATE, description="Maker fee fraction (e.g. 0.0002 = 0.02%)")
    taker_fee_rate: float = Field(default=DEFAULT_TAKER_FEE_RATE, description="Taker fee fraction (e.g. 0.0005 = 0.05%)")
    slippage_bps: float = Field(default=DEFAULT_SLIPPAGE_BPS, description="Slippage in basis points (1 bp = 0.01%)")
    funding_rate_per_8h: float = Field(default=0.0001, description="Average 8-hour funding rate (0.01%)")

    def calculate_entry_fill(self, price: float, is_taker: bool = True, is_long: bool = True) -> tuple[float, float, float]:
        """Calculate effective entry price with slippage and fee amount for 1 unit.

        Returns: (fill_price, slippage_paid, fee_paid)
        """
        slip_fraction = (self.slippage_bps / 10000.0) if is_taker else 0.0
        slippage = price * slip_fraction
        fill_price = (price + slippage) if is_long else (price - slippage)
        fee_rate = self.taker_fee_rate if is_taker else self.maker_fee_rate
        fee = fill_price * fee_rate
        return fill_price, slippage, fee

    def calculate_exit_fill(self, price: float, is_taker: bool = True, is_long: bool = True) -> tuple[float, float, float]:
        """Calculate effective exit price with slippage and fee amount for 1 unit.

        Returns: (fill_price, slippage_paid, fee_paid)
        """
        slip_fraction = (self.slippage_bps / 10000.0) if is_taker else 0.0
        slippage = price * slip_fraction
        fill_price = (price - slippage) if is_long else (price + slippage)
        fee_rate = self.taker_fee_rate if is_taker else self.maker_fee_rate
        fee = fill_price * fee_rate
        return fill_price, slippage, fee
