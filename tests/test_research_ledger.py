"""Tests for Research Ledger and experiment tracking."""

from quant_platform.domain.experiment import ExperimentRecord, ExperimentStatus, QuantMetrics
from quant_platform.research.ledger import ResearchLedger
from quant_platform.research.reporting import ReportGenerator


def test_research_ledger_lifecycle_and_deduplication(tmp_path):
    """Verify registration, query, and duplicate detection."""
    ledger = ResearchLedger(ledger_dir=tmp_path / "ledger")

    params = {"fast_period": 20, "slow_period": 50}
    exp_id = ledger.generate_experiment_id()

    record = ExperimentRecord(
        experiment_id=exp_id,
        hypothesis="Test hypothesis",
        strategy_id="baseline:ema_trend:v1",
        strategy_version="v1",
        feature_set_version="v1",
        parameters=params,
        parameter_hash=ledger._compute_parameter_hash(params),
        dataset_fingerprint="abc123fingerprint",
        date_range_start="2024-01-01",
        date_range_end="2024-01-31",
        cost_model={"maker": 0.0002, "taker": 0.0005},
        execution_model="EVENT_AWARE",
        risk_model="FIXED_RISK_1PCT",
        status=ExperimentStatus.COMPLETED,
    )

    ledger.register_experiment(record)

    # 1. Retrieve
    retrieved = ledger.get_experiment(exp_id)
    assert retrieved is not None
    assert retrieved.experiment_id == exp_id
    assert retrieved.strategy_id == "baseline:ema_trend:v1"

    # 2. List
    exp_list = ledger.list_experiments()
    assert len(exp_list) == 1
    assert exp_list[0]["experiment_id"] == exp_id

    # 3. Deduplication check
    dup = ledger.find_duplicate(
        strategy_id="baseline:ema_trend:v1",
        strategy_version="v1",
        parameters=params,
        dataset_fingerprint="abc123fingerprint",
        start_date="2024-01-01",
        end_date="2024-01-31",
        cost_model={"maker": 0.0002, "taker": 0.0005},
        seed=42,
    )
    assert dup is not None
    assert dup.experiment_id == exp_id

    # 4. Report generation
    reporter = ReportGenerator(reports_dir=tmp_path / "reports")
    html_file = reporter.generate_html_report(record)
    json_file = reporter.generate_json_export(record)
    assert html_file.exists()
    assert json_file.exists()
