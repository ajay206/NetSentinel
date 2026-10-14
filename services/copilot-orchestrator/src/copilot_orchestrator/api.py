"""copilot-orchestrator HTTP API (W9)."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from copilot_orchestrator.analyze import analyze
from copilot_orchestrator.clients.llm import LLM, OffLLM, OllamaLLM
from copilot_orchestrator.clients.upstream import Upstream
from copilot_orchestrator.models import AnalyzeRequest, AnalyzeResponse, NoEvidence

app = FastAPI(title="copilot-orchestrator", version="0.1.0")


def get_upstream() -> Upstream:
    return Upstream()


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
    return {"status": "ready", "llm": llm.name}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    req: AnalyzeRequest,
    upstream: Annotated[Upstream, Depends(get_upstream)],
    llm: Annotated[LLM, Depends(get_llm)],
) -> AnalyzeResponse:
    try:
        return await analyze(req, upstream, llm)
    except NoEvidence as exc:
        raise HTTPException(status_code=404, detail="No alarms for site in window") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8005")))
