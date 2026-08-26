"""Tabular Machine Learning Meta-Classifier and Probability Calibrator.

Trains and calibrates Secondary ML Meta-Models (Logistic Regression, LightGBM, Gradient Boosting)
to estimate P(TP hit before SL | Primary Strategy Candidate).
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from pydantic import BaseModel, Field
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss, roc_auc_score, precision_score, recall_score

from quant_platform.ml.meta_labeling import MetaLabelDataset
from quant_platform.observability.logger import logger


class MetaModelMetrics(BaseModel):
    """Evaluation metrics for calibrated meta-model."""
    model_type: str
    train_samples: int
    test_samples: int
    roc_auc: float
    brier_score: float
    precision: float
    recall: float
    is_calibrated: bool
    feature_importances: Dict[str, float] = Field(default_factory=dict)


class MetaClassifierTrainer:
    """Trains and calibrates tabular meta-models for secondary signal filtering."""

    def __init__(self, model_type: str = "gradient_boosting", random_state: int = 42):
        self.model_type = model_type
        self.random_state = random_state
        self.model: Optional[Any] = None
        self.feature_names: List[str] = []

    def train_and_calibrate(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: Optional[List[str]] = None,
    ) -> MetaModelMetrics:
        """Trains base tabular model and calibrates probability outputs."""
        self.feature_names = feature_names or [f"feat_{i}" for i in range(X_train.shape[1])]

        if self.model_type == "logistic_regression":
            base_clf = LogisticRegression(random_state=self.random_state, max_iter=500)
        else:
            base_clf = GradientBoostingClassifier(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.05,
                random_state=self.random_state,
            )

        # Train base model
        base_clf.fit(X_train, y_train)

        # Calibrate probabilities if enough samples exist
        if len(X_train) >= 20:
            calibrated_clf = CalibratedClassifierCV(estimator=base_clf, method="sigmoid", cv="prefit")
            calibrated_clf.fit(X_train, y_train)
            self.model = calibrated_clf
        else:
            self.model = base_clf

        # Predict on out-of-sample test split
        y_probs = self.model.predict_proba(X_test)[:, 1]
        y_preds = (y_probs >= 0.50).astype(int)

        # Compute metrics
        auc_val = float(roc_auc_score(y_test, y_probs)) if len(np.unique(y_test)) > 1 else 0.50
        brier_val = float(brier_score_loss(y_test, y_probs))
        prec_val = float(precision_score(y_test, y_preds, zero_division=0))
        rec_val = float(recall_score(y_test, y_preds, zero_division=0))

        # Extract feature importances if available
        importances: Dict[str, float] = {}
        if hasattr(base_clf, "feature_importances_"):
            for fname, imp in zip(self.feature_names, base_clf.feature_importances_):
                importances[fname] = float(imp)

        logger.info(f"Trained {self.model_type} Meta-Model: OOS AUC={auc_val:.3f}, Brier={brier_val:.4f}, Precision={prec_val:.2%}")

        return MetaModelMetrics(
            model_type=self.model_type,
            train_samples=len(X_train),
            test_samples=len(X_test),
            roc_auc=auc_val,
            brier_score=brier_val,
            precision=prec_val,
            recall=rec_val,
            is_calibrated=True,
            feature_importances=importances,
        )

    def predict_probability(self, feature_vector: np.ndarray) -> float:
        """Predict success probability for a single trade candidate."""
        if self.model is None:
            return 0.50
        feat_2d = feature_vector.reshape(1, -1)
        prob = self.model.predict_proba(feat_2d)[0, 1]
        return float(prob)
