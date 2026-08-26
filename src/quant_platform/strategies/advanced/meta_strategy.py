"""Meta-Labeled Secondary Filter Strategy Wrapper.

Wraps a Primary Strategy and applies a trained, calibrated Machine Learning Meta-Model
to filter out low-probability trade candidates prior to RiskEngine evaluation.
"""

from typing import List, Optional, Dict, Any
import numpy as np
import polars as pl

from quant_platform.domain.signal import SignalCandidate
from quant_platform.strategies.base import BaseStrategy, StrategyMetadata
from quant_platform.ml.meta_classifier import MetaClassifierTrainer
from quant_platform.observability.logger import logger


class MetaLabeledStrategy(BaseStrategy):
    """Secondary ML filter wrapper around any Primary quantitative strategy."""

    def __init__(
        self,
        primary_strategy: BaseStrategy,
        meta_trainer: MetaClassifierTrainer,
        probability_threshold: float = 0.52,
    ):
        meta = StrategyMetadata(
            strategy_id=f"{primary_strategy.metadata.strategy_id}_ML_Filtered",
            version="v1",
            hypothesis="Primary strategy with secondary calibrated ML meta-labeling filter.",
            parameters={
                **primary_strategy.metadata.parameters,
                "probability_threshold": probability_threshold,
                "ml_model_type": meta_trainer.model_type,
            },
        )
        super().__init__(metadata=meta)
        self.primary_strategy = primary_strategy
        self.meta_trainer = meta_trainer
        self.probability_threshold = probability_threshold

    def generate_signals(self, df: pl.DataFrame) -> List[SignalCandidate]:
        """Generate candidates from primary strategy and filter using ML meta-model."""
        primary_candidates = self.primary_strategy.generate_signals(df)
        if not primary_candidates or self.meta_trainer.model is None:
            return primary_candidates

        accepted: List[SignalCandidate] = []
        df_sorted = df.sort("close_time")
        timestamps = df_sorted["close_time"].to_list()
        time_to_idx = {t: i for i, t in enumerate(timestamps)}

        # Available feature columns
        feat_cols = [c for c in self.meta_trainer.feature_names if c in df_sorted.columns and c != "risk_reward_ratio"]
        feat_matrix = df_sorted.select(feat_cols).to_numpy() if feat_cols else np.zeros((len(df_sorted), 1))

        for cand in primary_candidates:
            cand_t = cand.timestamp
            if cand_t not in time_to_idx:
                accepted.append(cand)
                continue

            idx = time_to_idx[cand_t]
            row_feats = feat_matrix[idx].tolist() if feat_cols else [0.0]
            row_feats.append(float(cand.risk_reward_ratio or 2.0))

            prob = self.meta_trainer.predict_probability(np.array(row_feats, dtype=np.float32))

            if prob >= self.probability_threshold:
                cand.metadata["ml_probability"] = prob
                cand.metadata["ml_filter_accepted"] = True
                accepted.append(cand)
            else:
                logger.debug(f"[ML META FILTER] Rejected candidate at {cand_t}: P={prob:.2%} < {self.probability_threshold:.2%}")

        return accepted

    generate_signal_candidates = generate_signals
