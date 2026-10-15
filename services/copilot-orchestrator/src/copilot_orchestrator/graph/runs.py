"""Run lifecycle for the W17 agent graph: start, wait for approval, resume, read."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from . import tracing
from .agents import build_graph, now


class RunNotFound(LookupError):
    pass


class NotAwaitingApproval(RuntimeError):
    pass


class RunService:
    """Holds the compiled graph and its checkpointer (one LangGraph thread per run).

    ``deps_factory`` returns {"upstream", "llm", "actions"} for each invocation, so a resumed run
    gets fresh clients. The checkpointer is in-memory (lost on restart; ADR-017).
    """

    def __init__(self, deps_factory: Callable[[], Any], max_runs: int = 200) -> None:
        self.saver = InMemorySaver()
        self.graph = build_graph(self.saver)
        self.deps_factory = deps_factory
        self.meta: dict[str, dict[str, Any]] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.max_runs = max_runs

    def _cfg(self, run_id: str, deps: dict[str, Any]) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id, "deps": deps}}

    async def _invoke(self, run_id: str, payload: Any) -> dict[str, Any]:
        deps = await self.deps_factory()
        try:
            await self.graph.ainvoke(payload, self._cfg(run_id, deps))
        finally:
            await deps["upstream"].aclose()
        self.meta[run_id]["updatedAt"] = now()
        run = self.get(run_id)
        sent = self.meta[run_id].get("exported", 0)
        if await tracing.export(run, sent):
            self.meta[run_id]["exported"] = len(run["trace"])
        return run

    async def start(
        self, site_id: str, incident_id: str | None, window: str = "30m", trigger: str = "api"
    ) -> dict[str, Any]:
        run_id = "RUN-" + secrets.token_hex(5).upper()
        ts = now()
        self.meta[run_id] = {"createdAt": ts, "updatedAt": ts, "trigger": trigger}
        self.locks[run_id] = asyncio.Lock()
        if len(self.meta) > self.max_runs:  # bound memory: forget the oldest run
            oldest = next(iter(self.meta))
            self.meta.pop(oldest)
            self.locks.pop(oldest, None)
            self.saver.delete_thread(oldest)
        state = {
            "run_id": run_id,
            "site_id": site_id,
            "incident_id": incident_id,
            "window": window,
            "status": "running",
        }
        async with self.locks[run_id]:
            return await self._invoke(run_id, state)

    async def decide(self, run_id: str, approved: bool, by: str, note: str) -> dict[str, Any]:
        if run_id not in self.meta:
            raise RunNotFound(run_id)
        async with self.locks[run_id]:
            if self.get(run_id)["status"] != "awaiting_approval":
                raise NotAwaitingApproval(run_id)
            return await self._invoke(
                run_id, Command(resume={"approved": approved, "by": by, "note": note})
            )

    def get(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.meta:
            raise RunNotFound(run_id)
        snap = self.graph.get_state({"configurable": {"thread_id": run_id}})
        s = snap.values
        waiting = bool(snap.interrupts) if hasattr(snap, "interrupts") else bool(snap.next)
        status = "awaiting_approval" if waiting else s.get("status", "running")
        plan = s.get("plan")
        return {
            "runId": run_id,
            "incidentId": s.get("incident_id"),
            "siteId": s.get("site_id"),
            "status": status,
            "createdAt": self.meta[run_id]["createdAt"],
            "updatedAt": self.meta[run_id]["updatedAt"],
            "trigger": self.meta[run_id].get("trigger", "api"),
            "agentPath": s.get("agent_path", []),
            "messages": s.get("messages", []),
            "plan": {k: plan[k] for k in ("summary", "steps", "ticketDraft")} if plan else None,
            "answer": s.get("answer"),
            "generatedBy": s.get("generated_by"),
            "decision": s.get("decision"),
            "ticketId": s.get("ticket_id"),
            "kgWriteBack": s.get("kg"),
            "trace": s.get("trace", []),
            "report": s.get("report"),
            "tracing": {"langfuse": tracing.enabled()},
        }

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        ids = list(self.meta)[-limit:][::-1]
        return [self.get(i) for i in ids]
