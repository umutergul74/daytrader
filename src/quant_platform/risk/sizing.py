"""Position Sizing Models."""

import math
from typing import Optional
from pydantic import BaseModel
from quant_platform.config.constants import DEFAULT_MIN_NOTIONAL, DEFAULT_QTY_STEP


class SizingResult(BaseModel):
    quantity: float
    notional_value: float
    risk_amount_usdt: float
    is_valid: bool
    rejection_reason: Optional[str] = None


class PositionSizer:
    """Calculates order quantity based on capital allocation and risk parameters."""

    def __init__(
        self,
        min_notional: float = DEFAULT_MIN_NOTIONAL,
        qty_step: float = DEFAULT_QTY_STEP,
    ):
        self.min_notional = min_notional
        self.qty_step = qty_step

    def _round_step(self, qty: float) -> float:
        """Round quantity to allowable step size."""
        precision = max(0, -int(math.floor(math.log10(self.qty_step))))
        return round(math.floor(qty / self.qty_step) * self.qty_step, precision)

    def size_fixed_notional(self, entry_price: float, notional: float = 1000.0) -> SizingResult:
        """Size by fixed dollar notional."""
        if entry_price <= 0:
            return SizingResult(quantity=0.0, notional_value=0.0, risk_amount_usdt=0.0, is_valid=False, rejection_reason="Invalid price")

        qty = self._round_step(notional / entry_price)
        actual_notional = qty * entry_price

        if actual_notional < self.min_notional:
            return SizingResult(
                quantity=0.0,
                notional_value=actual_notional,
                risk_amount_usdt=0.0,
                is_valid=False,
                rejection_reason=f"Notional {actual_notional} below minimum {self.min_notional}",
            )

        return SizingResult(quantity=qty, notional_value=actual_notional, risk_amount_usdt=0.0, is_valid=True)

    def size_fixed_risk(
        self,
        equity: float,
        entry_price: float,
        stop_price: float,
        risk_fraction: float = 0.01,
    ) -> SizingResult:
        """Size such that hitting SL loses exactly risk_fraction * equity."""
        risk_distance = abs(entry_price - stop_price)
        if risk_distance <= 0 or entry_price <= 0:
            return SizingResult(quantity=0.0, notional_value=0.0, risk_amount_usdt=0.0, is_valid=False, rejection_reason="Zero stop distance")

        risk_usdt = equity * risk_fraction
        raw_qty = risk_usdt / risk_distance
        qty = self._round_step(raw_qty)
        actual_notional = qty * entry_price

        if actual_notional < self.min_notional:
            return SizingResult(
                quantity=0.0,
                notional_value=actual_notional,
                risk_amount_usdt=0.0,
                is_valid=False,
                rejection_reason=f"Risk-sized notional {actual_notional} below minimum {self.min_notional}",
            )

        actual_risk = qty * risk_distance
        return SizingResult(quantity=qty, notional_value=actual_notional, risk_amount_usdt=actual_risk, is_valid=True)
