"""Model router: ordered routes (local SLM first, cloud stub until Phase 3), per-route timeout
and a circuit breaker so a dead backend fails fast instead of eating every caller's timeout."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx


class RouteError(Exception):
    pass


class Backend(Protocol):
    name: str

    async def complete(
        self, messages: list[dict[str, str]], schema: dict[str, Any] | None
    ) -> str: ...


class OllamaBackend:
    """The only Ollama client in the repo (CI grep: scripts/check_llm_calls.py)."""

    def __init__(
        self,
        url: str,
        model: str,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url, self.model, self.timeout, self.transport = (
            url.rstrip("/"),
            model,
            timeout,
            transport,
        )
        self.name = f"ollama:{model}"

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any] | None) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 4096},
        }
        if schema:
            body["format"] = schema
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as c:
                r = await c.post(f"{self.url}/api/chat", json=body)
                r.raise_for_status()
                data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RouteError(f"ollama request failed: {type(exc).__name__}") from exc
        content = (data.get("message") or {}).get("content") if isinstance(data, dict) else None
        if not content:
            raise RouteError("ollama returned no content")
        return content


class CloudStub:
    """Phase-3 placeholder (telcogpt-mini / cloud). Never leaves the box; always unavailable."""

    name = "cloud:stub"

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any] | None) -> str:
        raise RouteError("cloud route is a stub until Phase 3")


class MockBackend:
    """LLM_ROUTES=mock (tests / demo without Ollama): scripted replies, last one repeats."""

    def __init__(self, replies: list[str], name: str = "mock") -> None:
        self.replies, self.name, self.calls = replies, name, []

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any] | None) -> str:
        self.calls.append(messages)
        return self.replies[min(len(self.calls), len(self.replies)) - 1]


@dataclass
class Breaker:
    threshold: int = 3
    cooldown: float = 30.0
    failures: int = 0
    opened_at: float | None = None
    clock: Any = field(default=time.monotonic, repr=False)

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half-open" if self.clock() - self.opened_at >= self.cooldown else "open"

    def allow(self) -> bool:
        return self.state != "open"

    def ok(self) -> None:
        self.failures, self.opened_at = 0, None

    def fail(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold or self.state == "half-open":
            self.opened_at = self.clock()


class Router:
    def __init__(self, backends: list[Backend], threshold: int = 3, cooldown: float = 30.0) -> None:
        self.backends = backends
        self.breakers = {b.name: Breaker(threshold, cooldown) for b in backends}

    async def complete(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None,
        prefer: str | None = None,
    ) -> tuple[str, str, list[dict[str, str]]]:
        """(content, route name, attempts [{route, outcome}]); RouteError if every route fails."""
        order = sorted(self.backends, key=lambda b: b.name != prefer) if prefer else self.backends
        attempts: list[dict[str, str]] = []
        for b in order:
            br = self.breakers[b.name]
            if not br.allow():
                attempts.append({"route": b.name, "outcome": "circuit-open"})
                continue
            try:
                content = await b.complete(messages, schema)
            except RouteError as exc:
                br.fail()
                attempts.append({"route": b.name, "outcome": str(exc)})
                continue
            br.ok()
            attempts.append({"route": b.name, "outcome": "ok"})
            return content, b.name, attempts
        raise RouteError(
            "no route available: " + "; ".join(f"{a['route']}={a['outcome']}" for a in attempts)
        )

    def status(self) -> list[dict[str, Any]]:
        return [
            {
                "route": b.name,
                "circuit": self.breakers[b.name].state,
                "failures": self.breakers[b.name].failures,
            }
            for b in self.backends
        ]


def from_env(
    spec: str, ollama_url: str, timeout: float, transport: httpx.AsyncBaseTransport | None = None
) -> list[Backend]:
    """``LLM_ROUTES`` e.g. ``ollama:qwen2.5:1.5b,cloud:stub`` (order = preference)."""
    out: list[Backend] = []
    for item in (s.strip() for s in spec.split(",")):
        if item.startswith("ollama:"):
            out.append(OllamaBackend(ollama_url, item.removeprefix("ollama:"), timeout, transport))
        elif item == "cloud:stub":
            out.append(CloudStub())
        elif item == "mock":
            out.append(MockBackend(['{"summary":"mock","rootCause":"mock","citations":[]}']))
        elif item:
            raise ValueError(f"unknown route {item!r}")
    return out
