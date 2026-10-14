"""LLM clients: local Ollama for real runs, a scripted mock for tests/CI, and an 'off' stub."""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from copilot_orchestrator.models import LLMError


class LLM(Protocol):
    name: str

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str: ...


class OllamaLLM:
    """Ollama /api/chat with structured output (``format`` = JSON schema), temperature 0."""

    def __init__(
        self,
        url: str = "http://localhost:11434",
        model: str = "qwen2.5:1.5b",
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.name = f"ollama:{model}"
        self._timeout = timeout
        self._transport = transport

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": 4096},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as c:
                resp = await c.post(f"{self.url}/api/chat", json=body)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"ollama request failed: {type(exc).__name__}") from exc
        content = (data.get("message") or {}).get("content") if isinstance(data, dict) else None
        if not content:
            raise LLMError("ollama returned no content")
        return content


class MockLLM:
    """Returns scripted responses in order (the last one repeats). Records every call."""

    name = "mock"

    def __init__(self, responses: list[str | dict[str, Any]]) -> None:
        if not responses:
            raise ValueError("MockLLM needs at least one response")
        self._responses = [r if isinstance(r, str) else json.dumps(r) for r in responses]
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        self.calls.append(messages)
        return self._responses[min(len(self.calls), len(self._responses)) - 1]


class OffLLM:
    """LLM=off: always fails fast, so /analyze returns the deterministic fallback answer."""

    name = "off"

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        raise LLMError("LLM disabled (LLM=off)")
