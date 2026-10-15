"""llm-gateway HTTP API (W18). POST /v1/complete is the only way services reach a model."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import Counter, deque
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from llm_gateway import guard, pii
from llm_gateway.router import RouteError, Router, from_env

logger = logging.getLogger("llm_gateway")


class Message(BaseModel):
    role: str = Field(pattern="^(system|user|assistant|tool)$")
    content: str


class CompleteRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    route: str | None = None


class Caller:
    def __init__(self, name: str, rpm: int, concurrency: int) -> None:
        self.name, self.rpm = name, rpm
        self.sem = asyncio.Semaphore(concurrency)
        self.hits: deque[float] = deque()

    def admit(self, now: float) -> bool:
        while self.hits and now - self.hits[0] > 60:
            self.hits.popleft()
        if len(self.hits) >= self.rpm:
            return False
        self.hits.append(now)
        return True


def parse_callers(spec: str, concurrency: int) -> dict[str, Caller]:
    """``LLM_GATEWAY_CALLERS=name:token:rpm,...`` -> {token: Caller}. Empty = dev mode (no auth)."""
    out: dict[str, Caller] = {}
    for item in filter(None, (s.strip() for s in spec.split(","))):
        name, token, *rest = item.split(":")
        out[token] = Caller(name, int(rest[0]) if rest else 60, concurrency)
    return out


class Gateway:
    def __init__(
        self,
        router: Router,
        callers: dict[str, Caller],
        max_chars: int = 24000,
        redact_prompts: bool = True,
    ) -> None:
        self.router, self.callers, self.max_chars = router, callers, max_chars
        self.redact_prompts = redact_prompts
        self.dev = Caller("dev", 120, 4)
        self.stats: Counter = Counter()
        self.redacted_types: Counter = Counter()
        self.last_route: str | None = None

    def caller(self, authorization: str | None) -> Caller:
        if not self.callers:
            return self.dev
        token = (authorization or "").removeprefix("Bearer ").strip()
        if token not in self.callers:
            raise HTTPException(401, "unknown caller token")
        return self.callers[token]

    async def complete(self, req: CompleteRequest, caller: Caller) -> dict[str, Any]:
        t0 = time.perf_counter()
        if not caller.admit(time.monotonic()):
            self.stats["rate_limited"] += 1
            raise HTTPException(429, f"rate limit for {caller.name}: {caller.rpm}/min")
        if sum(len(m.content) for m in req.messages) > self.max_chars:
            self.stats["too_large"] += 1
            raise HTTPException(413, f"prompt over {self.max_chars} chars")
        # Guard: only untrusted turns (the caller's own system prompt is trusted).
        reasons = sorted(
            {r for m in req.messages if m.role != "system" for r in guard.check(m.content).reasons}
        )
        if reasons:
            self.stats["blocked"] += 1
            logger.warning("blocked caller=%s reasons=%s", caller.name, reasons)
            raise HTTPException(400, {"error": "prompt_injection", "reasons": reasons})
        counts: Counter = Counter()
        msgs = []
        for m in req.messages:
            red = pii.redact(m.content)
            counts.update(red.counts)
            text = red.text if (self.redact_prompts and m.role != "system") else m.content
            msgs.append({"role": m.role, "content": text})
        async with caller.sem:
            try:
                content, route, attempts = await self.router.complete(msgs, req.schema_, req.route)
            except RouteError as exc:
                self.stats["unavailable"] += 1
                raise HTTPException(503, str(exc)) from exc
        out = pii.redact(content)
        counts.update(out.counts)
        self.stats["calls"] += 1
        self.redacted_types.update(counts)
        self.last_route = route
        latency = round((time.perf_counter() - t0) * 1000, 1)
        logger.info(
            "caller=%s route=%s ms=%s redacted=%s", caller.name, route, latency, dict(counts)
        )
        return {
            "content": out.text,
            "route": route,
            "model": route.split(":", 1)[-1],
            "latencyMs": latency,
            "attempts": attempts,
            "caller": caller.name,
            "redactions": {"total": sum(counts.values()), "types": dict(counts)},
        }


def build() -> Gateway:
    routes = from_env(
        os.getenv("LLM_ROUTES", "ollama:qwen2.5:1.5b,cloud:stub"),
        os.getenv("OLLAMA_URL", "http://localhost:11434"),
        float(os.getenv("LLM_TIMEOUT_S", "60")),
    )
    router = Router(
        routes,
        int(os.getenv("LLM_BREAKER_FAILURES", "3")),
        float(os.getenv("LLM_BREAKER_COOLDOWN_S", "30")),
    )
    callers = parse_callers(
        os.getenv("LLM_GATEWAY_CALLERS", ""), int(os.getenv("LLM_CALLER_CONCURRENCY", "2"))
    )
    return Gateway(
        router,
        callers,
        int(os.getenv("LLM_MAX_PROMPT_CHARS", "24000")),
        os.getenv("LLM_REDACT_PROMPTS", "1") != "0",
    )


def create_app(gw: Gateway | None = None) -> FastAPI:
    app = FastAPI(title="llm-gateway", version="0.1.0")
    app.state.gw = gw or build()

    @app.get("/health")
    async def health() -> dict[str, Any]:
        g: Gateway = app.state.gw
        return {
            "status": "ok",
            "routes": g.router.status(),
            "piiEngine": pii.engine_name(),
            "auth": "tokens" if g.callers else "dev",
        }

    @app.get("/v1/stats")
    async def stats() -> dict[str, Any]:
        g: Gateway = app.state.gw
        return {
            "activeRoute": g.last_route
            or (g.router.backends[0].name if g.router.backends else None),
            "routes": g.router.status(),
            "counters": dict(g.stats),
            "redactedTypes": dict(g.redacted_types),
            "devBanner": not g.callers,
        }

    @app.post("/v1/complete")
    async def complete(
        req: CompleteRequest, authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        g: Gateway = app.state.gw
        return await g.complete(req, g.caller(authorization))

    return app


app = create_app()
