"""MLflow tracking adapter for experiment logging."""

from pathlib import Path
from typing import Dict, Any, Optional
from quant_platform.config.settings import settings
from quant_platform.domain.experiment import ExperimentRecord
from quant_platform.observability.logger import logger


class MLflowAdapter:
    """Standardized MLflow experiment tracking adapter with graceful fallback."""

    def __init__(self, tracking_uri: Optional[str] = None, experiment_name: str = "ethusdt_quant_research"):
        self.tracking_uri = tracking_uri or str(settings.LOCAL_MLRUNS_DIR.resolve())
        self.experiment_name = experiment_name
        self._mlflow = None
        try:
            import mlflow
            self._mlflow = mlflow
            self._mlflow.set_tracking_uri(self.tracking_uri)
            self._mlflow.set_experiment(self.experiment_name)
        except ImportError:
            logger.debug("MLflow is not installed in current environment. Tracking disabled.")

    def log_experiment(self, record: ExperimentRecord, artifact_paths: Optional[Dict[str, Path]] = None) -> Optional[str]:
        """Log full experiment metadata and artifacts into MLflow."""
        if self._mlflow is None:
            logger.debug("Skipping MLflow logging because mlflow package is not available.")
            return None

        try:
            with self._mlflow.start_run(run_name=record.experiment_id) as run:
                # 1. Tags
                self._mlflow.set_tags({
                    "experiment_id": record.experiment_id,
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.strategy_version,
                    "status": record.status.value,
                    "git_sha": record.git_sha,
                    "symbol": record.symbol,
                    "dataset_fingerprint": record.dataset_fingerprint[:12],
                })

                # 2. Parameters
                flat_params = {
                    "strategy_id": record.strategy_id,
                    "timeframe": record.timeframe,
                    "date_start": record.date_range_start,
                    "date_end": record.date_range_end,
                    "random_seed": record.random_seed,
                }
                for k, v in record.parameters.items():
                    flat_params[f"param_{k}"] = str(v)
                for k, v in record.cost_model.items():
                    flat_params[f"cost_{k}"] = str(v)

                self._mlflow.log_params(flat_params)

                # 3. Metrics
                if record.metrics:
                    m_dict = {
                        "net_return_pct": record.metrics.total_net_return,
                        "gross_return_pct": record.metrics.gross_return,
                        "sharpe_ratio": record.metrics.sharpe_ratio,
                        "sortino_ratio": record.metrics.sortino_ratio,
                        "calmar_ratio": record.metrics.calmar_ratio,
                        "win_rate_pct": record.metrics.win_rate,
                        "profit_factor": record.metrics.profit_factor,
                        "max_drawdown_pct": record.metrics.max_drawdown_pct,
                        "trade_count": float(record.metrics.trade_count),
                        "expectancy": record.metrics.expectancy,
                        "average_r": record.metrics.average_r,
                        "median_r": record.metrics.median_r,
                    }
                    self._mlflow.log_metrics(m_dict)

                # 4. Artifacts
                if artifact_paths:
                    for name, path in artifact_paths.items():
                        if path.exists():
                            self._mlflow.log_artifact(str(path))

                logger.info(f"MLflow run logged successfully: {run.info.run_id}")
                return run.info.run_id
        except Exception as e:
            logger.warning(f"Failed to log to MLflow: {e}")
            return None
