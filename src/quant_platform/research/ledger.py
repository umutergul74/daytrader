"""Research Ledger for immutable experiment tracking and permanent knowledge retention."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from quant_platform.config.settings import settings
from quant_platform.domain.experiment import (
    ExperimentRecord,
    ExperimentStatus,
    QuantMetrics,
)
from quant_platform.observability.logger import logger


class ResearchLedger:
    """Persistent ledger storing all completed, rejected, and candidate research experiments."""

    def __init__(self, ledger_dir: Optional[Path] = None):
        self.ledger_dir = ledger_dir or settings.research_ledger_dir
        self.records_dir = self.ledger_dir / "records"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.ledger_dir / "experiments_index.json"

    def _compute_parameter_hash(self, params: Dict[str, Any]) -> str:
        """Compute deterministic MD5 hash of parameters."""
        serialized = json.dumps(params, sort_keys=True)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()[:10]

    def _compute_experiment_identity(
        self,
        strategy_id: str,
        strategy_version: str,
        param_hash: str,
        dataset_fingerprint: str,
        start_date: str,
        end_date: str,
        cost_model: Dict[str, Any],
        seed: int,
    ) -> str:
        """Compute exact identity fingerprint to prevent duplicate re-runs."""
        identity_payload = {
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "param_hash": param_hash,
            "dataset_fingerprint": dataset_fingerprint,
            "start_date": start_date,
            "end_date": end_date,
            "cost_model": cost_model,
            "seed": seed,
        }
        raw = json.dumps(identity_payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def generate_experiment_id(self) -> str:
        """Generate unique human-readable and sortable experiment ID."""
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        rand_suffix = hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:6]
        return f"EXP-{now_str}-{rand_suffix}"

    def register_experiment(self, record: ExperimentRecord) -> Path:
        """Persist experiment record into ledger and update global index."""
        record_file = self.records_dir / f"{record.experiment_id}.json"
        record_file.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        # Update index
        index = self.list_experiments()
        index_dict = {e["experiment_id"]: e for e in index}
        index_dict[record.experiment_id] = {
            "experiment_id": record.experiment_id,
            "strategy_id": record.strategy_id,
            "hypothesis": record.hypothesis,
            "status": record.status.value,
            "date_range": f"{record.date_range_start} - {record.date_range_end}",
            "net_return": record.metrics.total_net_return if record.metrics else 0.0,
            "sharpe": record.metrics.sharpe_ratio if record.metrics else 0.0,
            "win_rate": record.metrics.win_rate if record.metrics else 0.0,
            "trade_count": record.metrics.trade_count if record.metrics else 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.index_file.write_text(
            json.dumps(list(index_dict.values()), indent=2),
            encoding="utf-8",
        )
        logger.info(f"Registered experiment in ledger: {record.experiment_id} (Status: {record.status.value})")
        return record_file

    def list_experiments(self) -> List[Dict[str, Any]]:
        """List all indexed experiments."""
        if not self.index_file.exists():
            return []
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        """Load full experiment record by ID."""
        record_file = self.records_dir / f"{experiment_id}.json"
        if not record_file.exists():
            return None
        try:
            data = json.loads(record_file.read_text(encoding="utf-8"))
            return ExperimentRecord.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load experiment {experiment_id}: {e}")
            return None

    def find_similar_experiments(
        self,
        strategy_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find related past experiments by strategy ID or status."""
        all_exps = self.list_experiments()
        results = []
        for exp in all_exps:
            if strategy_id and exp.get("strategy_id") != strategy_id:
                continue
            if status and exp.get("status") != status:
                continue
            results.append(exp)
        return results

    def list_rejected_hypotheses(self) -> List[Dict[str, Any]]:
        """List all experiments permanently retained with REJECTED status."""
        return self.find_similar_experiments(status="rejected")

    def find_duplicate(
        self,
        strategy_id: str,
        strategy_version: str,
        parameters: Dict[str, Any],
        dataset_fingerprint: str,
        start_date: str,
        end_date: str,
        cost_model: Dict[str, Any],
        seed: int = 42,
    ) -> Optional[ExperimentRecord]:
        """Check if an identical experiment has already been recorded and return record."""
        is_dup, exp_id = self.is_duplicate_experiment(
            strategy_id,
            strategy_version,
            parameters,
            dataset_fingerprint,
            start_date,
            end_date,
            cost_model,
            seed,
        )
        if is_dup and exp_id:
            return self.get_experiment(exp_id)
        return None

    def is_duplicate_experiment(
        self,
        strategy_id: str,
        strategy_version: str,
        parameters: Dict[str, Any],
        dataset_fingerprint: str,
        start_date: str,
        end_date: str,
        cost_model: Dict[str, Any],
        seed: int = 42,
    ) -> Tuple[bool, Optional[str]]:
        """Check if an identical experiment has already been recorded."""
        param_hash = self._compute_parameter_hash(parameters)
        target_identity = self._compute_experiment_identity(
            strategy_id,
            strategy_version,
            param_hash,
            dataset_fingerprint,
            start_date,
            end_date,
            cost_model,
            seed,
        )

        for rec_path in self.records_dir.glob("EXP-*.json"):
            try:
                rec_data = json.loads(rec_path.read_text(encoding="utf-8"))
                rec_id = rec_data.get("experiment_id")
                rec_ident = self._compute_experiment_identity(
                    rec_data.get("strategy_id", ""),
                    rec_data.get("strategy_version", ""),
                    rec_data.get("parameter_hash", ""),
                    rec_data.get("dataset_fingerprint", ""),
                    rec_data.get("date_range_start", ""),
                    rec_data.get("date_range_end", ""),
                    rec_data.get("cost_model", {}),
                    rec_data.get("seed", 42),
                )
                if rec_ident == target_identity:
                    return True, rec_id
            except Exception:
                continue

        return False, None
