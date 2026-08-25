"""Tests for CLI application and commands."""

from typer.testing import CliRunner
from quant_platform.cli.app import cli

runner = CliRunner()


def test_cli_doctor_command():
    """Test `quant doctor` execution."""
    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0
    assert "System Diagnostics" in result.output


def test_cli_bootstrap_command():
    """Test `quant bootstrap` execution."""
    result = runner.invoke(cli, ["bootstrap"])
    assert result.exit_code == 0
    assert "initialized successfully" in result.output


def test_cli_research_list_empty():
    """Test `quant research list` on empty ledger."""
    result = runner.invoke(cli, ["research", "list"])
    assert result.exit_code == 0
