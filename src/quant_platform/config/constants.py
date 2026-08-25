"""System-wide quantitative and exchange constants."""

# Authoritative market identity
DEFAULT_MARKET_ID = "BINANCE_USDM_PERPETUAL:ETHUSDT"
DEFAULT_EXCHANGE = "binance"
DEFAULT_MARKET_TYPE = "usdm_futures"
DEFAULT_SYMBOL = "ETHUSDT"
DEFAULT_CONTRACT_TYPE = "perpetual"
CANONICAL_TIMEFRAME = "1m"

# Standard timeframes supported for causal aggregation
SUPPORTED_TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "12h",
    "1d", "1w"
]

# Binance Archive Endpoints
BINANCE_PUBLIC_DATA_BASE_URL = "https://data.binance.vision/data/futures/um"
BINANCE_FUTURES_REST_BASE_URL = "https://fapi.binance.com"

# Default Cost Model Parameters for USD-M Futures (VIP0 defaults)
DEFAULT_MAKER_FEE_RATE = 0.0002   # 0.02%
DEFAULT_TAKER_FEE_RATE = 0.0005   # 0.05%
DEFAULT_SLIPPAGE_BPS = 2.0         # 2 basis points
DEFAULT_MIN_NOTIONAL = 5.0         # 5 USDT
DEFAULT_TICK_SIZE = 0.01           # 0.01 USDT
DEFAULT_QTY_STEP = 0.001           # 0.001 ETH
