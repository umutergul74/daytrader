"""CLI commands package."""

from quant_platform.cli.commands.doctor import run_doctor
from quant_platform.cli.commands.data import app as data_app
from quant_platform.cli.commands.backtest import app as backtest_app
from quant_platform.cli.commands.research import app as research_app

__all__ = ["run_doctor", "data_app", "backtest_app", "research_app"]
