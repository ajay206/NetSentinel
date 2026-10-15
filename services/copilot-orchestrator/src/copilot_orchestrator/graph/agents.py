"""W17 agent graph: a supervisor routes between specialist agents (plan-and-execute).

    START -> supervisor -> triage -> supervisor -> rca -> supervisor -> remediation
          -> supervisor -> approval (interrupt: a human approves or rejects the plan)
          -> supervisor -> report -> END

* triage      gathers evidence (alarms, anomalies, fault prediction, Graph RAG runbooks)
* rca         asks the LLM for a cited answer (W9 citation guard; deterministic fallback) and
              checks the topology impact
* remediation turns the answer into a plan and a proposed ticket draft
* approval    pauses the graph (LangGraph ``interrupt``) until an operator decides
* report      on approval opens the ticket DRAFT (it still needs approval in the queue) and
              writes the finding back to the knowledge graph; always writes the report

State is checkpointed per run (``thread_id`` = run id), so a run survives the wait for the
human. Tools / LLM live in the run config, not the state, so the state stays serialisable.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from copilot_orchestrator.analyze import gather, llm_answer
from copilot_orchestrator.models import AnalyzeRequest, Context

AGENTS = ("triage", "rca", "remediation", "approval", "report")
Agent = Literal["supervisor", "triage", "rca", "remediation", "approval", "report"]


class RunState(TypedDict, total=False):
    run_id: str
    incident_id: str | None
    site_id: str
    window: str
    next: str
    status: str
    agent_path: list[str]
    messages: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    ctx: dict[str, Any]
    answer: dict[str, Any]
    generated_by: str
    impact: dict[str, Any] | None
    plan: dict[str, Any] | None
    decision: dict[str, Any] | None
    ticket_id: str | None
    kg: dict[str, Any] | None
    report: str | None


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _deps(config: RunnableConfig) -> dict[str, Any]:
    return config["configurable"]["deps"]


def _step(
    state: RunState,
    agent: str,
    name: str,
    t0: float,
    tool_calls: list[dict[str, Any]],
    detail: str,
    ok: bool = True,
) -> dict[str, Any]:
    trace = list(state.get("trace", []))
    trace.append(
        {
            "seq": len(trace) + 1,
            "agent": agent,
            "name": name,
            "startedAt": now(),
            "durationMs": int((time.perf_counter() - t0) * 1000),
            "ok": ok,
            "toolCalls": tool_calls,
            "detail": detail,
        }
    )
    return {"trace": trace, "agent_path": [*state.get("agent_path", []), agent]}


def _say(state: RunState, agent: str, text: str, sources: list[str] | None = None) -> list:
    return [
        *state.get("messages", []),
        {"agent": agent, "text": text, "ts": now(), "sources": sources or []},
    ]


# --- supervisor ---------------------------------------------------------------------------


def route(state: RunState) -> str:
    """Deterministic supervisor policy: the next specialist whose output is missing."""
    if state.get("status") == "failed":
        return "report" if state.get("report") is None else END
    if "ctx" not in state:
        return "triage"
    if "answer" not in state:
        return "rca"
    if state.get("plan") is None:
        return "remediation"
    if state.get("decision") is None:
        return "approval"
    if state.get("report") is None:
        return "report"
    return END


async def supervisor(state: RunState) -> dict[str, Any]:
    nxt = route(state)
    out: dict[str, Any] = {"next": nxt}
    if not state.get("agent_path"):
        out["agent_path"] = ["supervisor"]
        out["messages"] = _say(
            state,
            "supervisor",
            f"Investigating {state.get('incident_id') or state['site_id']}: triage → RCA → "
            "remediation → human approval → report.",
        )
    return out


# --- specialists --------------------------------------------------------------------------


async def triage(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    t0 = time.perf_counter()
    deps = _deps(config)
    upstream, actions = deps["upstream"], deps["actions"]
    site_id = state["site_id"]
    before_u, before_a = len(upstream.tool_calls), len(actions.calls)
    if state.get("incident_id"):
        inc = await actions.incident(state["incident_id"])
        if inc and inc.get("rootSiteId"):
            site_id = str(inc["rootSiteId"])
    ctx, _ = await gather(
        upstream, AnalyzeRequest(siteId=site_id, window=state.get("window", "30m"))
    )
    calls = actions.calls[before_a:] + upstream.tool_calls[before_u:]
    out: dict[str, Any] = {"site_id": site_id, "ctx": ctx.model_dump()}
    if not ctx.alarms:
        out |= {"status": "failed"}
        out["messages"] = _say(
            state, "triage", f"No alarms at {site_id} in the window; nothing to analyse."
        )
        return out | _step(state, "triage", "gather evidence", t0, calls, "no alarms", ok=False)
    fault = ctx.fault or {}
    root = ctx.alarms[0]
    text = (
        f"Root alarm {root.specificProblem} at {root.siteId} ({root.perceivedSeverity}); "
        f"{len(ctx.alarms)} alarms, {len(ctx.anomalies)} KPI anomalies; classifier says "
        f"{fault.get('faultType', 'unknown')}; {len(ctx.runbooks)} runbooks "
        f"({ctx.retrievalMode} retrieval)."
    )
    out["messages"] = _say(state, "triage", text, [root.id, *[r.runbookId for r in ctx.runbooks]])
    detail = (
        f"{len(ctx.alarms)} alarms · {len(ctx.anomalies)} anomalies · {len(ctx.runbooks)} runbooks"
    )
    return out | _step(state, "triage", "gather evidence", t0, calls, detail)


async def rca(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    t0 = time.perf_counter()
    deps = _deps(config)
    llm, actions = deps["llm"], deps["actions"]
    before_a = len(actions.calls)
    ctx = Context.model_validate(state["ctx"])
    answer, generated_by, attempts, errors = await llm_answer(ctx, llm)
    impact = await actions.impact(state["site_id"])
    calls = [
        {
            "name": f"llm:{llm.name}",
            "ok": generated_by == "llm",
            "durationMs": 0,
            "transport": "llm",
        }
    ]
    calls += actions.calls[before_a:]
    text = (
        f"{answer.suspectedCause} (fault {answer.faultType}, confidence {answer.confidence:.0%})."
    )
    if impact:
        lost, isolated = impact.get("cellsLost", 0), impact.get("sitesIsolated", 0)
        text += f" Impact: {lost} cells lost at {isolated} isolated sites."
    sources = sorted({s for c in answer.evidence for s in c.sources})
    detail = f"{generated_by} after {attempts} attempt(s)" + (f"; {errors[-1]}" if errors else "")
    return {
        "answer": answer.model_dump(),
        "generated_by": generated_by,
        "impact": impact,
        "messages": _say(state, "rca", text, sources),
    } | _step(state, "rca", "root-cause analysis", t0, calls, detail)


async def remediation(state: RunState) -> dict[str, Any]:
    t0 = time.perf_counter()
    a = state["answer"]
    ctx = state["ctx"]
    steps = [
        {"text": s["text"], "runbookId": s["runbookId"], "section": s["section"]}
        for s in a["steps"]
    ]
    sev = "critical" if a["confidence"] >= 0.7 else "major"
    where = state.get("incident_id") or state["site_id"]
    desc = [a["suspectedCause"], "", "Evidence:"]
    desc += [f"- {c['text']} [{', '.join(c['sources'])}]" for c in a["evidence"]]
    desc += ["", "Plan:"] + [
        f"{i}. {s['text']} ({s['runbookId']} §{s['section']})" for i, s in enumerate(steps, 1)
    ]
    fault_words = a["faultType"].replace("_", " ")
    plan = {
        "summary": f"{len(steps)} step(s) for {fault_words} at {state['site_id']}",
        "steps": steps,
        "ticketDraft": {
            "title": f"{fault_words.capitalize()} at {state['site_id']} ({where})"[:200],
            "severity": sev,
            "description": "\n".join(desc)[:4000],
        },
        "graphNodes": ctx.get("graphNodes", []),
    }
    text = (
        f"Proposed plan: {plan['summary']}. "
        "Waiting for an operator to approve before drafting the ticket."
    )
    return {
        "plan": plan,
        "status": "awaiting_approval",
        "messages": _say(state, "remediation", text, [s["runbookId"] for s in steps]),
    } | _step(state, "remediation", "plan remediation", t0, [], plan["summary"])


async def approval(state: RunState) -> dict[str, Any]:
    """Human-in-the-loop: the graph stops here until POST /v2/runs/{id}/approval resumes it."""
    t0 = time.perf_counter()
    decision = interrupt({"plan": state["plan"], "question": "Approve this remediation plan?"})
    approved = bool(decision.get("approved"))
    by, note = str(decision.get("by", "operator")), str(decision.get("note", ""))
    msgs = [
        *state.get("messages", []),
        {
            "agent": "human",
            "text": f"{'Approved' if approved else 'Rejected'} by {by}"
            + (f": {note}" if note else ""),
            "ts": now(),
            "sources": [],
        },
    ]
    return {
        "decision": {"approved": approved, "by": by, "note": note, "at": now()},
        "status": "running",
        "messages": msgs,
    } | _step(
        {**state, "messages": msgs},
        "approval",
        "human approval",
        t0,
        [],
        f"{'approved' if approved else 'rejected'} by {by}",
    )


async def report(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    t0 = time.perf_counter()
    actions = _deps(config)["actions"]
    before = len(actions.calls)
    out: dict[str, Any] = {}
    lines = [
        f"# Copilot run {state['run_id']}",
        "",
        f"Target: {state.get('incident_id') or state['site_id']} (site {state['site_id']})",
    ]
    if state.get("status") == "failed":
        lines += ["", "Outcome: no evidence (no alarms in the window)."]
        out["status"] = "failed"
    else:
        a, plan, d = state["answer"], state["plan"], state["decision"] or {}
        lines += [
            "",
            f"Suspected cause: {a['suspectedCause']}",
            f"Fault: {a['faultType']} ({a['confidence']:.0%}, {state.get('generated_by')})",
        ]
        lines += ["", "Plan:"] + [
            f"{i}. {s['text']} ({s['runbookId']} §{s['section']})"
            for i, s in enumerate(plan["steps"], 1)
        ]
        lines += [
            "",
            f"Decision: {'approved' if d.get('approved') else 'rejected'} by {d.get('by')}"
            + (f" — {d.get('note')}" if d.get("note") else ""),
        ]
        if d.get("approved"):
            draft = dict(
                plan["ticketDraft"],
                siteId=state["site_id"],
                runbookIds=[s["runbookId"] for s in plan["steps"]][:10],
            )
            draft["faultType"] = a["faultType"]
            draft["sourceIds"] = sorted({s for c in a["evidence"] for s in c["sources"]})[:30]
            if state.get("incident_id"):
                draft["incidentId"] = state["incident_id"]
            t = await actions.open_ticket_draft(draft)
            out["ticket_id"] = t.get("id") if t else None
            finding = {
                "runId": state["run_id"],
                "siteId": state["site_id"],
                "incidentId": state.get("incident_id"),
                "faultType": a["faultType"],
                "confidence": a["confidence"],
                "summary": a["suspectedCause"][:500],
                "approvedBy": d.get("by", "operator"),
                "runbookIds": draft["runbookIds"],
                "ticketId": out["ticket_id"],
            }
            kg = await actions.record_rca(finding)
            out["kg"] = {
                "ok": kg is not None,
                "detail": f"(:RcaFinding {state['run_id']})-[:ROOT_CAUSE]->"
                f"(:Site {state['site_id']})"
                if kg
                else "write-back failed (graph profile off?)",
            }
            lines += [
                f"Ticket draft: {out['ticket_id'] or 'FAILED (ticket-service unreachable?)'}"
                " — awaiting approval in the queue",
                f"Knowledge graph: {out['kg']['detail']}",
            ]
            out["status"] = "completed"
        else:
            lines += ["No ticket drafted; nothing written to the knowledge graph."]
            out["status"] = "rejected"
    out["report"] = "\n".join(lines)
    text = {
        "completed": f"Done. Ticket draft {out.get('ticket_id')} is in the approval queue.",
        "rejected": "Plan rejected; closing the run without a ticket.",
        "failed": "Run ended: no evidence.",
    }[out["status"]]
    out["messages"] = _say(
        state, "report", text, [out["ticket_id"]] if out.get("ticket_id") else []
    )
    return out | _step(
        state, "report", "report + write-back", t0, actions.calls[before:], out["status"]
    )


def build_graph(checkpointer: Any) -> Any:
    g = StateGraph(RunState)
    g.add_node("supervisor", supervisor)
    for name, fn in (
        ("triage", triage),
        ("rca", rca),
        ("remediation", remediation),
        ("approval", approval),
        ("report", report),
    ):
        g.add_node(name, fn)
        g.add_edge(name, "supervisor")
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", lambda s: s["next"], [*AGENTS, END])
    return g.compile(checkpointer=checkpointer)
