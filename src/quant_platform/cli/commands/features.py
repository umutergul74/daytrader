"""Features and Catalog CLI Commands."""

import typer
from rich.console import Console
from rich.table import Table

from quant_platform.features.catalog import FeatureCatalog, FeatureLifecycle

features_app = typer.Typer(help="Inspect quantitative features, definitions, and accumulated evidence.")
console = Console()


@features_app.command("list")
def list_features():
    """List all registered features and their research lifecycle status."""
    features = FeatureCatalog.list_all()

    table = Table(title="Quantitative Feature Catalog", show_header=True, header_style="bold cyan")
    table.add_column("Feature ID", style="bold")
    table.add_column("Category", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Timeframe")
    table.add_column("Experiments", justify="right")

    for f in features:
        table.add_row(
            f"{f.feature_id}:{f.version}",
            f.category,
            f.lifecycle_status.value,
            f.required_timeframe,
            str(f.experiment_count),
        )

    console.print(table)


@features_app.command("show")
def show_feature(feature_id: str = typer.Argument(..., help="Feature ID (e.g. smc:fvg_three_candle)")):
    """Show detailed mathematical specification and evidence for a feature."""
    feat = FeatureCatalog.get(feature_id)
    if not feat:
        console.print(f"[bold red]Feature '{feature_id}' not found in catalog.[/bold red]")
        raise typer.Exit(1)

    table = Table(title=f"Feature Specification: {feat.feature_id}:{feat.version}", show_header=True)
    table.add_column("Attribute", style="bold cyan")
    table.add_column("Value")

    table.add_row("Category", feat.category)
    table.add_row("Lifecycle Status", feat.lifecycle_status.value)
    table.add_row("Mathematical Definition", feat.mathematical_definition)
    table.add_row("Source Implementation", feat.source_implementation)
    table.add_row("Availability Semantics", feat.availability_semantics)
    table.add_row("Causality Status", feat.causality_status)
    table.add_row("Experiment Count", str(feat.experiment_count))
    table.add_row("Evidence Summary", feat.evidence_summary)

    console.print(table)
