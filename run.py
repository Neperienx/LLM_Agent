"""Interactive entry point for the LLM Agent playground.

This script makes it easy to either create a brand-new pipeline project or
launch one of the existing JSON definitions without memorising any CLI
arguments.  It guides users through collecting pipeline metadata, writing a
prompt template, and finally running the orchestrator with the provided
inputs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.orchestrator import PipelineRunner
from core.pipeline_loader import PipelineLoader

BASE_DIR = Path(__file__).resolve().parent
PIPELINES_DIR = BASE_DIR / "pipelines"
TEMPLATES_DIR = BASE_DIR / "templates"

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _prompt(message: str, *, default: str | None = None) -> str:
    """Prompt the user for input, falling back to a default when provided."""

    suffix = f" [{default}]" if default else ""
    while True:
        response = input(f"{message}{suffix}: ").strip()
        if response:
            return response
        if default is not None:
            return default
        print("Please enter a value.")


def _confirm(message: str, *, default: bool = False) -> bool:
    """Ask the user for a yes/no confirmation."""

    prompt_default = "Y/n" if default else "y/N"
    while True:
        response = input(f"{message} ({prompt_default}): ").strip().lower()
        if not response:
            return default
        if response in {"y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Please answer with 'y' or 'n'.")


def _collect_inputs() -> dict[str, str]:
    """Interactively gather pipeline input definitions."""

    print("\nDefine the inputs your pipeline expects. Leave the name blank to finish.")
    inputs: dict[str, str] = {}
    while True:
        name = input("Input name: ").strip()
        if not name:
            break
        dtype = input("  Type (default: string): ").strip() or "string"
        inputs[name] = dtype
    return inputs


def _collect_prompt_template(slug: str) -> str:
    """Ask the user to provide the prompt template contents."""

    print(
        "\nEnter the Jinja prompt template for your LLM call."
        " When you are done, type END on its own line and press Enter."
    )
    lines: list[str] = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    prompt_body = "\n".join(lines).strip()
    if not prompt_body:
        prompt_body = (
            "You are an assistant. Summarise the project inputs in a friendly tone.\n"
            "Inputs: {{ inputs }}\n"
        )
        print(
            "\nNo prompt content entered. Using a default helper prompt so the pipeline "
            "remains runnable."
        )
    return prompt_body + "\n"


def _write_project_files(slug: str, pipeline: dict[str, Any], prompt_text: str) -> None:
    """Persist the generated pipeline JSON and template."""

    PIPELINES_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    pipeline_path = PIPELINES_DIR / f"{slug}.json"
    template_path = TEMPLATES_DIR / f"{slug}.j2"

    pipeline_path.write_text(json.dumps(pipeline, indent=2) + "\n", encoding="utf-8")
    template_path.write_text(prompt_text, encoding="utf-8")

    print("\nCreated the following project files:")
    print(f"- Pipeline definition: {pipeline_path}")
    print(f"- Prompt template:    {template_path}")


def _create_project() -> None:
    """Guide the user through building a new pipeline project."""

    print("\n=== Create a New Pipeline Project ===")
    while True:
        slug = _prompt(
            "Project identifier (letters, numbers, hyphen, underscore)",
        )
        if not SLUG_PATTERN.match(slug):
            print("Identifiers may only include letters, numbers, hyphens, and underscores.")
            continue
        pipeline_path = PIPELINES_DIR / f"{slug}.json"
        template_path = TEMPLATES_DIR / f"{slug}.j2"
        if pipeline_path.exists() or template_path.exists():
            print("A project with that identifier already exists. Choose another name.")
            continue
        break

    default_name = slug.replace("_", " ").replace("-", " ").title()
    name = _prompt("Display name", default=default_name)
    description = input("Short description (optional): ").strip()

    inputs = _collect_inputs()
    prompt_text = _collect_prompt_template(slug)

    pipeline: dict[str, Any] = {
        "version": 1,
        "name": name,
        "description": description,
        "inputs": inputs,
        "steps": [
            {
                "id": "draft",
                "type": "llm_call",
                "prompt": f"{slug}.j2",
                "params": {"temperature": 0.2, "max_tokens": 600},
                "outputs": {"response": "content"},
            },
            {
                "id": "save_response",
                "type": "store",
                "inputs": {"response": "draft.response"},
                "filename": "response.md",
                "content_key": "response",
            },
        ],
    }

    _write_project_files(slug, pipeline, prompt_text)

    if _confirm("Run this new project now?"):
        _run_pipeline(pipeline, label=name)


def _run_pipeline(pipeline: dict[str, Any], *, label: str | None = None) -> None:
    """Collect user inputs and execute the provided pipeline."""

    label = label or pipeline.get("name") or "pipeline"
    print(f"\n=== Running '{label}' ===")

    inputs_schema = pipeline.get("inputs", {})
    inputs: dict[str, Any] = {}
    for key, dtype in inputs_schema.items():
        prompt = f"Value for '{key}'"
        if dtype:
            prompt += f" ({dtype})"
        value = _prompt(prompt)
        inputs[key] = value

    runner = PipelineRunner()
    try:
        result = runner.run(pipeline, inputs)
    except Exception as exc:  # pragma: no cover - defensive for runtime issues
        print(f"\nAn error occurred while running the pipeline: {exc}")
        return

    print("\nPipeline run completed successfully!")
    print(f"Run ID: {result['run_id']}")
    print(f"Artifacts saved to: {result['artifacts_path']}")


def _open_existing_project() -> None:
    """List available pipelines and allow the user to run one."""

    print("\n=== Open an Existing Project ===")
    loader = PipelineLoader()
    pipelines = loader.list_pipelines()
    if not pipelines:
        print("No pipelines found. Create one first or add JSON files to the 'pipelines/' directory.")
        return

    for idx, info in enumerate(pipelines, start=1):
        description = f" - {info['description']}" if info.get("description") else ""
        print(f"{idx}. {info['name']}{description}")
        print(f"   File: {info['path']}")

    while True:
        selection = input("Select a project by number (or type a path): ").strip()
        if not selection:
            print("Please select a project.")
            continue

        pipeline_def: dict[str, Any]
        label: str | None = None

        if selection.isdigit():
            index = int(selection) - 1
            if index < 0 or index >= len(pipelines):
                print("Number out of range. Try again.")
                continue
            chosen = pipelines[index]
            pipeline_def = loader.load(chosen["path"])
            label = chosen.get("name")
            break

        try:
            pipeline_def = loader.load(selection)
            label = pipeline_def.get("name") or selection
            break
        except FileNotFoundError:
            print("No pipeline found for that selection. Try again.")

    _run_pipeline(pipeline_def, label=label)


def main() -> None:
    print("Welcome to the LLM Agent playground!")
    while True:
        print("\nChoose an option:")
        print("1. Create a new project")
        print("2. Open an existing project")
        print("Q. Quit")

        choice = input("> ").strip().lower()
        if choice in {"1", "create", "c", "new", "n"}:
            _create_project()
        elif choice in {"2", "open", "o", "existing", "e"}:
            _open_existing_project()
        elif choice in {"q", "quit", "exit"}:
            print("Goodbye!")
            return
        else:
            print("Unrecognised option. Please choose 1, 2, or Q.")


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
