from __future__ import annotations

from pathlib import Path
from typing import Any
import json

class PipelineLoader:
    """Loads pipeline definitions stored as JSON files."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent / "pipelines"

    def list_pipelines(self) -> list[dict[str, Any]]:
        pipelines: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            pipelines.append({
                "name": data.get("name", path.stem),
                "path": str(path),
                "description": data.get("description", ""),
                "inputs": data.get("inputs", {}),
            })
        return pipelines

    def load(self, name_or_path: str) -> dict[str, Any]:
        path = Path(name_or_path)
        if not path.exists():
            path = self.base_dir / f"{name_or_path}.json"
        if not path.exists():
            raise FileNotFoundError(f"Pipeline '{name_or_path}' not found in {self.base_dir}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
