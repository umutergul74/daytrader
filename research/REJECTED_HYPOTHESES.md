# Permanently Retained Rejected Hypotheses & Negative Findings

## 1. Unfiltered RSI Mean Reversion (`baseline:rsi_reversion:v1`)
- **Hypothesis**: Buying RSI < 30 and selling RSI > 70 unconditionally produces positive expectancy.
- **Empirical Result**: REJECTED (-0.41% net return after taker fees and slippage).
- **Failure Mode**: In strong trending markets, RSI remains in overbought/oversold territory while price continues strongly in the trend direction, incurring repeated stop-outs.
- **Action Taken**: Gated RSI mean reversion to `regime_state == "RANGING"` in `RegimeAwareMeanReversionStrategy`.

## 2. Instantaneous Swing Reversal Without Confirmation
- **Hypothesis**: Trading pivot high/low reversals at the exact candle of the peak yields alpha.
- **Empirical Result**: REJECTED (Theoretical simulator artifact due to lookahead bias).
- **Correction**: Swings must be confirmed at bar $i + R$ before any signal generation can be permitted.
