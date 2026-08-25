# Permanent Research Knowledge Base

Accumulated empirical evidence, validated concepts, and quantitative findings for Binance USDⓈ-M ETHUSDT Perpetual Futures.

---

## 1. Validated Baseline Findings
- **Data Resolution**: 1-minute canonical contract klines provide the exact temporal fidelity needed for intraday execution simulation without lookahead artifacts.
- **Transaction Friction**: Taker fee (0.05%) + Slippage (2 bps) on both entry and exit requires strategies to capture $\ge 0.15\%$ gross move to achieve positive net expectancy on short timeframes.
- **Intrabar Ambiguity**: Conservative stop loss prioritization prevents inflated backtest win rates on candles with wide high-low spans.
