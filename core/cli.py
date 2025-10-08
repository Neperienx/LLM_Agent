from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .orchestrator import PipelineRunner
from .pipeline_loader import PipelineLoader

app = typer.Typer(help="Agent pipeline CLI")


def parse_params(params: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in params:
        if "=" not in item:
            raise typer.BadParameter(f"Parameters must be in key=value format. Got '{item}'")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


@app.command()
def list() -> None:  # type: ignore[override]
    """List available pipelines."""
    loader = PipelineLoader()
    for pipeline in loader.list_pipelines():
        typer.echo(f"- {pipeline['name']} ({pipeline['path']})")
        if pipeline.get("description"):
            typer.echo(f"    {pipeline['description']}")


@app.command()
def run(
    pipeline: str = typer.Argument(..., help="Pipeline name or path"),
    param: list[str] = typer.Option([], "--param", "-p", help="Input parameter key=value"),
    artifacts_dir: Optional[Path] = typer.Option(None, help="Override artifacts output directory"),
) -> None:
    """Run a pipeline with the provided parameters."""
    loader = PipelineLoader()
    pipeline_def = loader.load(pipeline)
    inputs = parse_params(param)
    runner = PipelineRunner(artifacts_dir=artifacts_dir)
    result = runner.run(pipeline_def, inputs)
    typer.echo(f"Run ID: {result['run_id']}")
    typer.echo(f"Artifacts: {result['artifacts_path']}")


if __name__ == "__main__":
    app()
