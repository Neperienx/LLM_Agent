from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.orchestrator import PipelineRunner
from core.pipeline_loader import PipelineLoader

app = FastAPI(title="LLM Agent Platform", version="0.1.0")
loader = PipelineLoader()
runner = PipelineRunner()


class RunRequest(BaseModel):
    pipeline: str
    inputs: dict[str, Any]


class RunResponse(BaseModel):
    run_id: str
    artifacts_path: str
    steps: list[dict[str, Any]]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/pipelines")
def list_pipelines() -> list[dict[str, Any]]:
    return loader.list_pipelines()


@app.post("/runs", response_model=RunResponse)
def trigger_run(request: RunRequest) -> RunResponse:
    try:
        pipeline_def = loader.load(request.pipeline)
    except FileNotFoundError as exc:  # pragma: no cover - simple error mapping
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = runner.run(pipeline_def, request.inputs)
    return RunResponse(**result)


@app.get("/artifacts/{run_id}")
def get_artifact_manifest(run_id: str) -> dict[str, Any]:
    path = Path(runner.artifacts_dir) / f"run-{run_id}" / "run.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse.model_validate_json(path.read_text()).model_dump()
