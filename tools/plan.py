from __future__ import annotations

from typing import Any


def plan_chapters(outline_md: str) -> dict[str, Any]:
    """Convert a markdown outline into a list of chapter plans."""
    chapters: list[dict[str, str]] = []
    for line in outline_md.splitlines():
        line = line.strip("- •\t ")
        if not line:
            continue
        heading = line.strip()
        summary = heading
        chapters.append({"title": heading, "summary": summary})
    return {"chapters": chapters}
