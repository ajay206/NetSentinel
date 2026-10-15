"""LLM clients: llm-gateway for real runs (W18, no direct model calls), a mock, and 'off'."""

from __future__ import annotations

import json
import ssl
from typing import Any, Protocol

import httpx

from copilot_orchestrator.models import LLMError


class LLM(Protocol):
    name: str

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str: ...


class GatewayLLM:
    """Every model call goes through llm-gateway (W18): routing, guardrails, PII redaction.

    ``last`` keeps the gateway's route / latency / redaction info for the response and trace.
    A guard block (400), rate limit (429) or no route (503) raises LLMError -> fallback answer.
    """

    name = "llm-gateway"

    def __init__(
        self,
        url: str = "http://localhost:8010",
        token: str | None = None,
        timeout: float = 90.0,
        transport: httpx.AsyncBaseTransport | None = None,
        ca: str | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        # Step 21: https://llm-gateway:8443 with the dev CA; the hybrid X25519MLKEM768 group is
        # enforced process-wide by OPENSSL_CONF (infra/pqc/openssl-hybrid.cnf).
        self._verify: ssl.SSLContext | bool = ssl.create_default_context(cafile=ca) if ca else True
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._timeout = timeout
        self._transport = transport
        self.last: dict[str, Any] | None = None

    async def complete(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        body = {"messages": messages, "schema": schema}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport, verify=self._verify
            ) as c:
                resp = await c.post(f"{self.url}/v1/complete", json=body, headers=self._headers)
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"llm-gateway request failed: {type(exc).__name__}") from exc
        if resp.status_code != 200:
            detail = data.get("detail") if isinstance(data, dict) else None
            if isinstance(detail, dict) and detail.get("error") == "prompt_injection":
                self.last = {"route": None, "latencyMs": 0, "blocked": detail.get("reasons", [])}
                raise LLMError(
                    "blocked by llm-gateway guard: " + ",".join(detail.get("reasons", []))
                )
            raise LLMError(f"llm-gateway {resp.status_code}: {str(detail)[:120]}")
        self.last = {
            "route": data.get("route"),
            "latencyMs": data.get("latencyMs", 0),
            "redactions": (data.get("redactions") or {}).get("total", 0),
            "blocked": [],
        }
        content = data.get("content")
        if not content:
            raise LLMError("llm-gateway returned no content")
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
