"""HTML and JSON Backtest Report Generator."""

from pathlib import Path
from typing import Optional, Dict, Any
import json

from quant_platform.config.settings import settings
from quant_platform.domain.experiment import ExperimentRecord
from quant_platform.backtest.ledger import TradeLedger
from quant_platform.observability.logger import logger


class ReportGenerator:
    """Generates standalone interactive HTML reports and structured JSON exports."""

    def __init__(self, reports_dir: Optional[Path] = None):
        self.reports_dir = reports_dir or settings.LOCAL_REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_html_report(self, record: ExperimentRecord, ledger: Optional[TradeLedger] = None) -> Path:
        """Render publication-quality standalone HTML report."""
        report_file = self.reports_dir / f"report_{record.experiment_id}.html"

        m = record.metrics
        trades = ledger.trades if ledger else []

        # Generate HTML content
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Report - {record.experiment_id}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #4ade80;
            --accent-red: #f87171;
            --accent-purple: #c084fc;
            --border-color: #334155;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 30px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            color: var(--accent-blue);
            font-size: 26px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            background-color: #0284c7;
            color: white;
        }}
        .badge-completed {{ background-color: #16a34a; }}
        .badge-rejected {{ background-color: #dc2626; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
        }}
        .card .title {{
            font-size: 13px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }}
        .card .value {{
            font-size: 24px;
            font-weight: 700;
        }}
        .value.positive {{ color: var(--accent-green); }}
        .value.negative {{ color: var(--accent-red); }}
        .value.neutral {{ color: var(--accent-blue); }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 14px;
        }}
        th, td {{
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            background-color: #0f172a;
            color: var(--text-muted);
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #243248;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            margin: 30px 0 15px 0;
            color: var(--accent-purple);
            border-left: 4px solid var(--accent-purple);
            padding-left: 10px;
        }}
        pre {{
            background-color: #0b1120;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            border: 1px solid var(--border-color);
            font-size: 13px;
            color: #38bdf8;
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <span class="badge badge-{record.status.value}">{record.status.value}</span>
        <h1>{record.strategy_id} ({record.strategy_version})</h1>
        <div style="color: var(--text-muted); font-size: 14px;">
            Experiment ID: <strong>{record.experiment_id}</strong> | Date Range: {record.date_range_start} &rarr; {record.date_range_end} | Symbol: {record.symbol} ({record.timeframe})
        </div>
        <div style="margin-top: 10px; font-style: italic; color: #cbd5e1;">
            Hypothesis: "{record.hypothesis}"
        </div>
    </div>

    <!-- Metric Cards -->
    <div class="grid">
        <div class="card">
            <div class="title">Total Net Return</div>
            <div class="value {'positive' if (m and m.total_net_return >= 0) else 'negative'}">
                {f"{m.total_net_return:+.2f}%" if m else "N/A"}
            </div>
        </div>
        <div class="card">
            <div class="title">Win Rate</div>
            <div class="value neutral">
                {f"{m.win_rate:.1f}%" if m else "N/A"}
            </div>
        </div>
        <div class="card">
            <div class="title">Profit Factor</div>
            <div class="value {'positive' if (m and m.profit_factor >= 1.0) else 'negative'}">
                {f"{m.profit_factor:.2f}" if m else "N/A"}
            </div>
        </div>
        <div class="card">
            <div class="title">Sharpe Ratio</div>
            <div class="value neutral">
                {f"{m.sharpe_ratio:.2f}" if m else "N/A"}
            </div>
        </div>
        <div class="card">
            <div class="title">Max Drawdown</div>
            <div class="value negative">
                {f"{m.max_drawdown_pct:.2f}%" if m else "N/A"}
            </div>
        </div>
        <div class="card">
            <div class="title">Trade Count</div>
            <div class="value neutral">
                {m.trade_count if m else 0}
            </div>
        </div>
    </div>

    <!-- Detailed Metrics Table -->
    <div class="section-title">Statistical Performance Breakdown</div>
    <div class="card">
        <table>
            <tr><th>Metric</th><th>Value</th><th>Metric</th><th>Value</th></tr>
            <tr>
                <td>Gross Return</td><td>{m.gross_return if m else 0}%</td>
                <td>Total Fees Paid</td><td>${m.total_fees if m else 0:.2f}</td>
            </tr>
            <tr>
                <td>Sortino Ratio</td><td>{m.sortino_ratio if m else 0:.2f}</td>
                <td>Calmar Ratio</td><td>{m.calmar_ratio if m else 0:.2f}</td>
            </tr>
            <tr>
                <td>Average R-Multiple</td><td>{m.average_r if m else 0:.2f}R</td>
                <td>Median R-Multiple</td><td>{m.median_r if m else 0:.2f}R</td>
            </tr>
            <tr>
                <td>Average Winner</td><td>${m.average_winner if m else 0:.2f}</td>
                <td>Average Loser</td><td>${m.average_loser if m else 0:.2f}</td>
            </tr>
            <tr>
                <td>Long Trades (Win %)</td><td>{m.long_trades if m else 0} ({m.long_win_rate if m else 0:.1f}%)</td>
                <td>Short Trades (Win %)</td><td>{m.short_trades if m else 0} ({m.short_win_rate if m else 0:.1f}%)</td>
            </tr>
            <tr>
                <td>Max Consecutive Wins</td><td>{m.consecutive_wins_max if m else 0}</td>
                <td>Max Consecutive Losses</td><td>{m.consecutive_losses_max if m else 0}</td>
            </tr>
            <tr>
                <td>Market Exposure</td><td>{m.exposure_pct if m else 0:.1f}%</td>
                <td>Intrabar Ambiguities</td><td>{m.intrabar_ambiguity_count if m else 0}</td>
            </tr>
        </table>
    </div>

    <!-- Parameters and Audit Metadata -->
    <div class="section-title">Audit Metadata & Configuration</div>
    <div class="card">
        <table>
            <tr><th>Attribute</th><th>Value</th></tr>
            <tr><td>Dataset Fingerprint</td><td><code>{record.dataset_fingerprint}</code></td></tr>
            <tr><td>Git SHA</td><td><code>{record.git_sha}</code> (Dirty: {record.git_dirty})</td></tr>
            <tr><td>Execution Model</td><td>{record.execution_model}</td></tr>
            <tr><td>Risk Model</td><td>{record.risk_model}</td></tr>
            <tr><td>Cost Model</td><td><code>{json.dumps(record.cost_model)}</code></td></tr>
            <tr><td>Strategy Parameters</td><td><code>{json.dumps(record.parameters)}</code></td></tr>
        </table>
    </div>

    <!-- Trade Ledger Preview -->
    <div class="section-title">Trade Ledger (First 20 Executions)</div>
    <div class="card" style="overflow-x: auto;">
        <table>
            <thead>
                <tr>
                    <th>Trade ID</th><th>Side</th><th>Entry Time (UTC)</th><th>Entry $</th><th>Exit $</th><th>Net PnL</th><th>R</th><th>MFE%</th><th>MAE%</th><th>Exit Reason</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f'''<tr>
                    <td>{t.trade_id}</td>
                    <td style="color: {'#4ade80' if t.side == 'LONG' else '#f87171'}">{t.side}</td>
                    <td>{t.entry_time}</td>
                    <td>${t.entry_price:.2f}</td>
                    <td>${t.exit_price:.2f}</td>
                    <td style="color: {'#4ade80' if t.net_pnl > 0 else '#f87171'}">${t.net_pnl:+.2f}</td>
                    <td>{t.r_multiple:+.2f}R</td>
                    <td>{t.mfe:.1f}%</td>
                    <td>{t.mae:.1f}%</td>
                    <td>{t.exit_reason.value}</td>
                </tr>''' for t in trades[:20]]) if trades else '<tr><td colspan="10">No trades executed</td></tr>'}
            </tbody>
        </table>
    </div>
</div>
</body>
</html>
"""
        report_file.write_text(html_template, encoding="utf-8")
        logger.info(f"HTML report generated: {report_file}")
        return report_file

    def generate_json_export(self, record: ExperimentRecord) -> Path:
        """Export raw machine-readable JSON."""
        json_file = self.reports_dir / f"export_{record.experiment_id}.json"
        json_file.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return json_file
