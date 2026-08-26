"""Machine Learning Meta-Labeling Framework.

Implements Marcos López de Prado's Triple-Barrier Method for secondary ML filtering
and Purged Walk-Forward Cross-Validation splitting.
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import polars as pl
from pydantic import BaseModel, Field

from quant_platform.domain.signal import SignalCandidate, SignalDirection
from quant_platform.domain.trade import TradeDirection
from quant_platform.observability.logger import logger


class MetaLabelDataset(BaseModel):
    """Container for meta-labeling feature matrix and binary labels."""
    feature_names: List[str]
    X: List[List[float]]
    y: List[int]
    timestamps_ms: List[int]
    sample_weights: List[float] = Field(default_factory=list)


class MetaLabelingEngine:
    """Computes triple-barrier labels on Primary Strategy trade candidates."""

    @staticmethod
    def compute_triple_barrier_labels(
        df_15m: pl.DataFrame,
        candidates: List[SignalCandidate],
        max_holding_bars: int = 20,
    ) -> MetaLabelDataset:
        """Labels trade candidates with 1 if TP is reached before SL, else 0."""
        if not candidates or df_15m.is_empty():
            return MetaLabelDataset(feature_names=[], X=[], y=[], timestamps_ms=[])

        df_sorted = df_15m.sort("open_time")
        open_ts = df_sorted["open_time"].to_list()
        close_ts = df_sorted["close_time"].to_list()
        highs = df_sorted["high"].to_list()
        lows = df_sorted["low"].to_list()

        time_to_idx: Dict[int, int] = {}
        for i, t in enumerate(open_ts):
            time_to_idx[int(t)] = i
        for i, t in enumerate(close_ts):
            time_to_idx[int(t)] = i

        # Define candidate feature column list
        feat_cols = [
            "atr_14", "rsi_14", "delta_1m", "rel_delta_1m", "trade_imbalance_1m",
            "open_interest", "oi_change_pct_15m", "oi_zscore_15m",
        ]
        avail_cols = [c for c in feat_cols if c in df_sorted.columns]

        feat_matrix = df_sorted.select(avail_cols).to_numpy() if avail_cols else np.zeros((len(df_sorted), 1))

        X_list: List[List[float]] = []
        y_list: List[int] = []
        ts_list: List[int] = []

        for cand in candidates:
            cand_t = cand.timestamp
            if cand_t not in time_to_idx:
                continue

            start_idx = time_to_idx[cand_t]
            if start_idx + 1 >= len(df_sorted):
                continue

            is_long = "LONG" in str(cand.direction).upper()
            entry_p = float(cand.entry_price)
            sl_p = float(cand.stop_loss) if cand.stop_loss else (entry_p * 0.99 if is_long else entry_p * 1.01)
            tp_p = float(cand.take_profit_1) if cand.take_profit_1 else (
                entry_p + 2.0 * abs(entry_p - sl_p) if is_long else entry_p - 2.0 * abs(entry_p - sl_p)
            )

            end_idx = min(len(df_sorted), start_idx + 1 + max_holding_bars)
            is_tp_hit = False

            for curr_i in range(start_idx + 1, end_idx):
                h = highs[curr_i]
                l = lows[curr_i]

                if is_long:
                    if l <= sl_p:
                        is_tp_hit = False
                        break
                    if h >= tp_p:
                        is_tp_hit = True
                        break
                else:
                    if h >= sl_p:
                        is_tp_hit = False
                        break
                    if l <= tp_p:
                        is_tp_hit = True
                        break

            # Build feature vector
            row_feats = feat_matrix[start_idx].tolist() if avail_cols else [0.0]
            row_feats.append(float(cand.risk_reward_ratio or 2.0))

            X_list.append(row_feats)
            y_list.append(1 if is_tp_hit else 0)
            ts_list.append(cand_t)

        all_names = list(avail_cols) + ["risk_reward_ratio"]
        pos_ratio = float(np.mean(y_list)) if y_list else 0.0
        logger.info(f"Generated {len(y_list)} labeled meta-samples (Positive class: {pos_ratio:.1%})")
        return MetaLabelDataset(
            feature_names=all_names,
            X=X_list,
            y=y_list,
            timestamps_ms=ts_list,
            sample_weights=[1.0] * len(y_list),
        )

    @staticmethod
    def purged_walk_forward_split(
        dataset: MetaLabelDataset,
        train_ratio: float = 0.70,
        embargo_samples: int = 2,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Performs chronological split with embargo to eliminate label leakage."""
        n = len(dataset.y)
        if n < 4:
            raise ValueError(f"Insufficient samples ({n}) for walk-forward ML split.")

        train_size = max(2, int(n * train_ratio))
        test_start = min(n - 1, train_size + embargo_samples)

        X_arr = np.array(dataset.X, dtype=np.float32)
        y_arr = np.array(dataset.y, dtype=np.int64)

        X_train, y_train = X_arr[:train_size], y_arr[:train_size]
        X_test, y_test = X_arr[test_start:], y_arr[test_start:]

        if len(X_test) == 0:
            X_test, y_test = X_arr[train_size:], y_arr[train_size:]

        return X_train, y_train, X_test, y_test
