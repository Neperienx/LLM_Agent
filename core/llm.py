from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    content: str
    usage: dict[str, Any]


class LocalLLMClient:
    """A tiny stub client that produces deterministic text for demo purposes."""

    def complete(self, prompt: str, **params: Any) -> LLMResponse:
        temperature = params.get("temperature", 0.2)
        max_tokens = params.get("max_tokens", 512)
        body = prompt.strip()
        header = "# Local LLM Draft\n"
        footer = (
            "\n\n---\n"
            "_Generated locally with temperature {temperature}, max_tokens {max_tokens}._"
        ).format(temperature=temperature, max_tokens=max_tokens)
        content = f"{header}{body}{footer}"
        return LLMResponse(content=content, usage={"prompt_tokens": len(prompt.split()), "completion_tokens": len(content.split())})
