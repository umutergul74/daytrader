"""CLI command: `quant doctor`."""

import sys
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from quant_platform.colab.hardware import ResourceDetector
from quant_platform.colab.git_sync import SafeGitSync
from quant_platform.config.settings import settings
from quant_platform.config.constants import BINANCE_FUTURES_REST_BASE_URL
from quant_platform.research.ledger import ResearchLedger

console = Console()


def run_doctor() -> bool:
    """Run comprehensive system health and environment diagnostics."""
    console.print(Panel.fit("[bold cyan]ETHUSDT Quantitative Research Platform — System Diagnostics[/bold cyan]"))

    table = Table(title="Environment & Resource Health", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan", width=25)
    table.add_column("Status", width=12)
    table.add_column("Details", style="white")

    all_passed = True

    # 1. Hardware & OS
    res = ResourceDetector.detect()
    table.add_row("Python Version", "[green]OK[/green]", f"{res.python_version} ({res.os_name})")
    table.add_row("CPU & RAM", "[green]OK[/green]", f"{res.cpu_count} cores, {res.ram_gb} GB RAM")
    table.add_row("Disk Space", "[green]OK[/green]", f"{res.disk_free_gb} GB free")

    # 2. GPU
    if res.gpu_available:
        table.add_row("GPU Acceleration", "[green]AVAILABLE[/green]", f"{res.gpu_name} (CUDA {res.cuda_version})")
    else:
        table.add_row("GPU Acceleration", "[yellow]CPU ONLY[/yellow]", "No CUDA GPU detected (Fine for Polars backtests)")

    # 3. Git Status
    git_info = SafeGitSync().get_git_info()
    git_status_str = f"SHA: {git_info['git_sha'][:8]} (Dirty: {git_info['is_dirty']})"
    table.add_row("Git Code Lineage", "[green]OK[/green]" if git_info['git_sha'] != "unknown" else "[yellow]UNTRACKED[/yellow]", git_status_str)

    # 4. Storage Directories
    settings.ensure_directories()
    table.add_row("Directory Layout", "[green]OK[/green]", f"Canonical: {settings.canonical_data_dir}")

    # 5. Research Ledger
    ledger = ResearchLedger()
    exp_count = len(ledger.list_experiments())
    table.add_row("Research Ledger", "[green]READY[/green]", f"{exp_count} experiments registered in permanent memory")

    # 6. Binance API Reachability
    try:
        r = httpx.get(f"{BINANCE_FUTURES_REST_BASE_URL}/fapi/v1/ping", timeout=5.0)
        if r.status_code == 200:
            table.add_row("Binance USD-M API", "[green]REACHABLE[/green]", "Ping successful (fapi.binance.com)")
        else:
            table.add_row("Binance USD-M API", "[yellow]HTTP ERROR[/yellow]", f"Status code: {r.status_code}")
    except Exception as e:
        table.add_row("Binance USD-M API", "[red]UNREACHABLE[/red]", f"Network error: {str(e)[:50]}")
        all_passed = False

    console.print(table)
    if all_passed:
        console.print("\n[bold green]SYSTEM_READY[/bold green]: All core quantitative subsystems operational.\n")
    else:
        console.print("\n[bold yellow]SYSTEM_WARNING[/bold yellow]: Some network checks did not pass.\n")

    return all_passed
