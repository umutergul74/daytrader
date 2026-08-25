"""Market domain models and strict market identity."""

from enum import Enum
from pydantic import BaseModel, Field


class Exchange(str, Enum):
    BINANCE = "binance"


class ProductType(str, Enum):
    USDM_FUTURES = "usdm_futures"
    COIN_M_FUTURES = "coin_m_futures"
    SPOT = "spot"


class ContractType(str, Enum):
    PERPETUAL = "perpetual"
    CURRENT_QUARTER = "current_quarter"
    NEXT_QUARTER = "next_quarter"


class MarketIdentity(BaseModel):
    """Authoritative, unambiguous market identity."""
    exchange: Exchange = Exchange.BINANCE
    product_type: ProductType = ProductType.USDM_FUTURES
    symbol: str = "ETHUSDT"
    contract_type: ContractType = ContractType.PERPETUAL

    @property
    def canonical_id(self) -> str:
        return f"{self.exchange.value.upper()}_{self.product_type.value.upper()}_{self.contract_type.value.upper()}:{self.symbol}"

    def __str__(self) -> str:
        return self.canonical_id
