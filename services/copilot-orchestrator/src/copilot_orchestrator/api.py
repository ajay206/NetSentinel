"""copilot-orchestrator HTTP API (W9)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from copilot_orchestrator.analyze import analyze
from copilot_orchestrator.clients.llm import LLM, OffLLM, OllamaLLM
from copilot_orchestrator.clients.mcp_client import McpUpstream
from copilot_orchestrator.clients.upstream import ToolRecorder, Upstream
from copilot_orchestrator.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    NoEvidence,
    UpstreamError,
)

app = FastAPI(title="copilot-orchestrator", version="0.1.0")


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
    if os.getenv("LLM", "ollama") == "off":
        return OffLLM()
    return OllamaLLM(
        url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b"),
        timeout=float(os.getenv("LLM_TIMEOUT_S", "60")),
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8005")))
