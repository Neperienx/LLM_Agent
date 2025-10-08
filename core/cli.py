from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from .orchestrator import PipelineRunner
from .pipeline_loader import PipelineLoader


def _parse_params(values: Iterable[str]) -> dict[str, str]:
    """Turn key=value pairs into a dictionary.

    Parameters are provided from the command line in the form ``key=value``. This helper
    validates the shape and converts the list into a mapping so it can be passed to the
    pipeline runner as structured inputs.
    """

    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Parameters must be in key=value format (got '{item}')")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


def _cmd_list_pipelines(_: argparse.Namespace) -> int:
    loader = PipelineLoader()
    pipelines = loader.list_pipelines()
    if not pipelines:
        print("No pipelines were found. Add JSON definitions under the 'pipelines/' folder.")
        return 0

    for pipeline in pipelines:
        print(f"- {pipeline['name']} ({pipeline['path']})")
        description = pipeline.get("description")
        if description:
            print(f"    {description}")
    return 0


def _cmd_run_pipeline(args: argparse.Namespace) -> int:
    loader = PipelineLoader()
    pipeline_def = loader.load(args.pipeline)
    try:
        inputs = _parse_params(args.params)
    except ValueError as exc:  # pragma: no cover - defensive branch
        print(f"Error: {exc}")
        return 1

    runner = PipelineRunner(artifacts_dir=args.artifacts_dir)
    result = runner.run(pipeline_def, inputs)
    print(f"Run ID: {result['run_id']}")
    print(f"Artifacts: {result['artifacts_path']}")
    return 0


def _cmd_visualize(_: argparse.Namespace) -> int:
    from tools.pipeline_visualizer import launch

    launch()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local LLM pipelines without any web services.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="Show available pipelines")
    list_parser.set_defaults(func=_cmd_list_pipelines)

    run_parser = subparsers.add_parser("run", help="Execute a pipeline with the provided inputs")
    run_parser.add_argument("pipeline", help="Pipeline name or JSON path")
    run_parser.add_argument(
        "--param",
        "-p",
        dest="params",
        action="append",
        default=[],
        metavar="key=value",
        help="Pipeline input parameter",
    )
    run_parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Optional directory where run artifacts should be stored",
    )
    run_parser.set_defaults(func=_cmd_run_pipeline)

    visualize_parser = subparsers.add_parser(
        "visualize",
        help="Launch a GUI to inspect prompts and step dependencies",
    )
    visualize_parser.set_defaults(func=_cmd_visualize)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
