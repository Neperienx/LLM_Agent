from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptService:
    """Loads and renders Jinja2 templates for prompts."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = templates_dir or Path(__file__).resolve().parent.parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(enabled_extensions=("j2", "jinja2"), default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_path: str, variables: dict[str, Any]) -> str:
        template = self.env.get_template(template_path)
        return template.render(**variables)
