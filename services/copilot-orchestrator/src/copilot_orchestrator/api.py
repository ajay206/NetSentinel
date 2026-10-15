"""copilot-orchestrator HTTP API (W9)."""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from copilot_orchestrator.analyze import analyze
from copilot_orchestrator.clients.llm import LLM, GatewayLLM, OffLLM
from copilot_orchestrator.clients.mcp_client import McpUpstream
from copilot_orchestrator.clients.upstream import ToolRecorder, Upstream
from copilot_orchestrator.graph import trigger
from copilot_orchestrator.graph.actions import GatewayActions
from copilot_orchestrator.graph.runs import NotAwaitingApproval, RunNotFound, RunService
from copilot_orchestrator.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    NoEvidence,
    UpstreamError,
)


class RunRequest(BaseModel):
    """W17: run the agents on an incident (its root site) or a site."""

    model_config = ConfigDict(extra="forbid")
    incidentId: str | None = Field(default=None, pattern=r"^INC-[0-9A-F]{10}$")
    siteId: str | None = Field(default=None, pattern=r"^SITE-\d{3}$")
    window: str = Field(default="30m", pattern=r"^\d{1,3}m$")


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool
    note: str = Field(default="", max_length=500)


async def _deps() -> dict[str, Any]:
    upstream: ToolRecorder = (
        McpUpstream.from_env() if os.getenv("TOOLS", "mcp") == "mcp" else Upstream()
    )
    return {"upstream": upstream, "llm": get_llm(), "actions": GatewayActions()}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.runs = RunService(_deps)
    task = None
    if os.getenv("AGENT_TRIGGER", "off") == "kafka":
        task = asyncio.create_task(trigger.consume(app.state.runs))
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="copilot-orchestrator", version="0.2.0", lifespan=lifespan)


def get_runs() -> RunService:
    return app.state.runs


async def get_upstream() -> AsyncIterator[ToolRecorder]:
    """TOOLS=mcp (default, W10): evidence via mcp-server tools. TOOLS=http: direct calls (W9)."""
    upstream: ToolRecorder = (
        McpUpstream.from_env() if os.getenv("TOOLS", "mcp") == "mcp" else Upstream()
    )
    try:
        yield upstream
    finally:
        await upstream.aclose()


def get_llm() -> LLM:
    if os.getenv("LLM", "gateway") == "off":
        return OffLLM()
    return GatewayLLM(
        url=os.getenv("LLM_GATEWAY_URL", "http://localhost:8010"),
        token=os.getenv("LLM_GATEWAY_TOKEN") or None,
        timeout=float(os.getenv("LLM_TIMEOUT_S", "90")),
        ca=os.getenv("LLM_GATEWAY_CA") or None,
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(llm: Annotated[LLM, Depends(get_llm)]) -> dict[str, Any]:
    return {"status": "ready", "llm": llm.name, "tools": os.getenv("TOOLS", "mcp")}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    req: AnalyzeRequest,
    upstream: Annotated[ToolRecorder, Depends(get_upstream)],
    llm: Annotated[LLM, Depends(get_llm)],
) -> AnalyzeResponse:
    try:
        return await analyze(req, upstream, llm)
    except UpstreamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except NoEvidence as exc:
        raise HTTPException(status_code=404, detail="No alarms for site in window") from exc


# --- W17: multi-agent runs (LangGraph) --------------------------------------------------------


@app.post("/v2/runs")
async def start_run(
    req: RunRequest, runs: Annotated[RunService, Depends(get_runs)]
) -> dict[str, Any]:
    """Run supervisor -> triage -> RCA -> remediation; stops at the human approval node."""
    if not req.incidentId and not req.siteId:
        raise HTTPException(status_code=422, detail="give incidentId or siteId")
    return await runs.start(req.siteId or "SITE-000", req.incidentId, req.window)


@app.get("/v2/runs")
async def list_runs(runs: Annotated[RunService, Depends(get_runs)]) -> dict[str, Any]:
    return {"items": runs.list()}


@app.get("/v2/runs/{run_id}")
async def get_run(run_id: str, runs: Annotated[RunService, Depends(get_runs)]) -> dict[str, Any]:
    try:
        return runs.get(run_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


@app.post("/v2/runs/{run_id}/approval")
async def decide_run(
    run_id: str,
    req: ApprovalRequest,
    runs: Annotated[RunService, Depends(get_runs)],
    x_ns_user: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Human approval node: resume the paused graph with the operator's decision."""
    by = (
        x_ns_user if x_ns_user and re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", x_ns_user) else "operator"
    )
    try:
        return await runs.decide(run_id, req.approved, by, req.note.strip())
    except RunNotFound as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except NotAwaitingApproval as exc:
        raise HTTPException(status_code=409, detail="run is not waiting for approval") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8005")))
