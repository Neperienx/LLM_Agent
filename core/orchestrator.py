from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .llm import LocalLLMClient
from .prompt_service import PromptService


@dataclass
class StepResult:
    id: str
    type: str
    outputs: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineRunner:
    def __init__(
        self,
        artifacts_dir: Path | None = None,
        prompt_service: PromptService | None = None,
        llm_client: LocalLLMClient | None = None,
    ) -> None:
        self.artifacts_dir = artifacts_dir or Path(__file__).resolve().parent.parent / "artifacts"
        self.prompt_service = prompt_service or PromptService()
        self.llm_client = llm_client or LocalLLMClient()
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def run(self, pipeline: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
        run_dir = self.artifacts_dir / f"run-{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)

        context: dict[str, Any] = {"inputs": inputs, "steps": {}}
        step_results: list[StepResult] = []

        for step in pipeline.get("steps", []):
            step_id = step["id"]
            step_type = step["type"]
            if step_type == "llm_call":
                result = self._run_llm_step(step, context)
            elif step_type == "transform":
                result = self._run_transform_step(step, context)
            elif step_type == "store":
                result = self._run_store_step(step, context, run_dir)
            else:
                raise ValueError(f"Unsupported step type: {step_type}")

            context["steps"][step_id] = result.outputs
            step_results.append(result)

        run_manifest = {
            "run_id": run_id,
            "pipeline": pipeline.get("name"),
            "inputs": inputs,
            "steps": [
                {
                    "id": r.id,
                    "type": r.type,
                    "outputs": r.outputs,
                    "metadata": r.metadata,
                }
                for r in step_results
            ],
        }
        with (run_dir / "run.json").open("w", encoding="utf-8") as f:
            json.dump(run_manifest, f, indent=2)

        return {"run_id": run_id, "artifacts_path": str(run_dir), "steps": run_manifest["steps"]}

    def _build_step_context(self, context: dict[str, Any]) -> dict[str, Any]:
        render_context = {"inputs": context["inputs"]}
        for step_id, values in context["steps"].items():
            render_context[step_id] = values
        return render_context

    def _run_llm_step(self, step: dict[str, Any], context: dict[str, Any]) -> StepResult:
        variables = self._build_step_context(context)
        variables.update(step.get("vars", {}))
        prompt_template = step["prompt"]
        prompt = self.prompt_service.render(prompt_template, variables)
        params = step.get("params", {})
        llm_response = self.llm_client.complete(prompt, **params)
        output_mappings = step.get("outputs", {"content": "content"})
        mapped_outputs: dict[str, Any] = {}
        for target, source in output_mappings.items():
            if source == "content":
                mapped_outputs[target] = llm_response.content
            elif source.startswith("metadata."):
                _, _, key = source.partition(".")
                mapped_outputs[target] = llm_response.usage.get(key)
            else:
                raise ValueError(f"Unsupported llm_call output source '{source}'")
        return StepResult(
            id=step["id"],
            type=step["type"],
            outputs=mapped_outputs,
            metadata={"usage": llm_response.usage},
        )

    def _run_transform_step(self, step: dict[str, Any], context: dict[str, Any]) -> StepResult:
        code = step.get("code")
        if not code or not code.startswith("python:"):
            raise ValueError("Transform steps currently support python:<module>.<callable>")
        _, target = code.split(":", 1)
        module_path, func_name = target.rsplit(".", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        call_inputs = self._resolve_inputs(step.get("inputs", {}), context)
        result = func(**call_inputs)
        if isinstance(result, dict):
            outputs = result
        else:
            outputs = {list(step.get("outputs", {}).keys())[0]: result}
        return StepResult(id=step["id"], type=step["type"], outputs=outputs)

    def _run_store_step(self, step: dict[str, Any], context: dict[str, Any], run_dir: Path) -> StepResult:
        inputs = self._resolve_inputs(step.get("inputs", {}), context)
        filename = step.get("filename", f"{step['id']}.md")
        content_key = step.get("content_key") or next(iter(inputs))
        content = inputs[content_key]
        output_path = run_dir / filename
        output_path.write_text(content, encoding="utf-8")
        return StepResult(id=step["id"], type=step["type"], outputs={"path": str(output_path)})

    def _resolve_inputs(self, mappings: dict[str, str], context: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, ref in mappings.items():
            resolved[key] = self._resolve_reference(ref, context)
        return resolved

    def _resolve_reference(self, reference: str, context: dict[str, Any]) -> Any:
        parts = reference.split(".")
        if parts[0] == "inputs":
            value: Any = context["inputs"]
            for part in parts[1:]:
                value = value[part]
            return value
        step_id = parts[0]
        value: Any = context["steps"].get(step_id, {})
        for part in parts[1:]:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list):
                value = value[int(part)]
            else:
                raise KeyError(f"Cannot traverse {reference}")
        return value
