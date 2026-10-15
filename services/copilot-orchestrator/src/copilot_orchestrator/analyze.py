"""W9 analyze flow: gather evidence -> local LLM -> Pydantic + citation checks -> retry/fallback."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from pydantic import ValidationError

from copilot_orchestrator.clients.llm import LLM
from copilot_orchestrator.clients.upstream import ToolRecorder
from copilot_orchestrator.models import (
    AlarmRef,
    AnalyzeRequest,
    AnalyzeResponse,
    AnomalyRef,
    Answer,
    AnswerInvalid,
    Claim,
    Context,
    LLMError,
    NoEvidence,
    RunbookRef,
    Step,
    UpstreamError,
)
from copilot_orchestrator.prompts.analyze import build_messages

ANSWER_SCHEMA: dict[str, Any] = Answer.model_json_schema()


_NODE_ID_RE = re.compile(r"SITE-\d{3}(-N\d{1,2}(-C\d{1,2})?)?|LNK-\d{3}")


def _camel_words(value: str | None) -> str:
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", value or "").lower()


async def gather(
    upstream: ToolRecorder, req: AnalyzeRequest
) -> tuple[Context, list[dict[str, Any]]]:
    """Collect alarms, fault prediction, runbooks and anomalies. Returns (context, raw alarms)."""
    raw_alarms = await upstream.alarms_for_site(req.site_id, req.window_minutes)
    alarms = [
        AlarmRef(
            id=str(a.get("id")),
            siteId=str(a.get("siteId")),
            specificProblem=str(a.get("specificProblem", "")),
            perceivedSeverity=str(a.get("perceivedSeverity", "")),
            alarmRaisedTime=str(a.get("alarmRaisedTime", "")),
            role=str((a.get("correlation") or {}).get("role", "none")),
        )
        for a in raw_alarms
    ]
    fault: dict[str, Any] | None = None
    runbooks: list[RunbookRef] = []
    if raw_alarms:
        root = raw_alarms[0]  # select_site_alarms puts the root / most severe first
        fault = await upstream.predict(root)
        fault_type = (fault or {}).get("faultType")
        query = " ".join(
            p
            for p in (
                str(root.get("siteId") or req.site_id),  # entity for Graph RAG linking
                root.get("specificProblem"),
                _camel_words(root.get("probableCause")),
                (fault_type or "").replace("_", " "),
            )
            if p
        )
        runbooks = [
            RunbookRef(
                runbookId=r["runbookId"],
                title=r.get("title", ""),
                section=r.get("section", ""),
                snippet=r.get("snippet", ""),
                nodeIds=[
                    str(n) for n in (r.get("nodeIds") or [])[:6] if _NODE_ID_RE.fullmatch(str(n))
                ],
            )
            for r in await upstream.runbooks(query, fault_type)
            if re.fullmatch(r"RB-[A-Z]{3}-\d{3}", str(r.get("runbookId", "")))
        ]
    anomalies = [
        AnomalyRef(
            id=f"ANOM-{i['cellId']}-{i['kpi']}-{i['ts']}",
            cellId=i["cellId"],
            kpi=i["kpi"],
            ts=i["ts"],
            score=float(i.get("score", 0)),
            direction=str(i.get("direction", "")),
        )
        for i in await upstream.anomalies_for_site(req.site_id)
    ]
    ctx = Context(
        site_id=req.site_id,
        window_minutes=req.window_minutes,
        alarms=alarms,
        anomalies=anomalies,
        fault=fault,
        runbooks=runbooks,
        retrievalMode="graph" if any(r.nodeIds for r in runbooks) else "hybrid",
        graphNodes=list(dict.fromkeys(n for r in runbooks for n in r.nodeIds))[:8],
    )
    return ctx, raw_alarms


def validate_answer(raw: str, ctx: Context) -> Answer:
    """Parse + schema-validate the LLM output, then enforce that every citation exists."""
    try:
        answer = Answer.model_validate(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise AnswerInvalid([f"not valid JSON ({exc.msg})"]) from exc
    except ValidationError as exc:
        msgs = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5]]
        raise AnswerInvalid(msgs) from exc
    allowed = ctx.source_ids()
    runbook_ids = {r.runbookId for r in ctx.runbooks}
    errors = [
        f"evidence cites unknown source {src!r}"
        for claim in answer.evidence
        for src in claim.sources
        if src not in allowed
    ]
    errors += [
        f"step uses runbookId {s.runbookId!r} not in context"
        for s in answer.steps
        if s.runbookId not in runbook_ids
    ]
    if runbook_ids and not answer.steps:
        errors.append("steps must use at least one runbook from the context")
    if errors:
        raise AnswerInvalid(errors)
    return answer


def fallback_answer(ctx: Context) -> Answer:
    """Deterministic answer from the evidence (LLM off, down, or never valid)."""
    if not ctx.alarms:
        raise NoEvidence()
    root = ctx.alarms[0]
    fault = ctx.fault or {}
    fault_type = str(fault.get("faultType") or "unknown")
    evidence = [
        Claim(
            text=f"{a.perceivedSeverity} {a.specificProblem} at {a.siteId} ({a.role})",
            sources=[a.id],
        )
        for a in ctx.alarms[:3]
    ]
    evidence += [
        Claim(
            text=f"{an.kpi} anomaly on {an.cellId} (score {an.score:.1f}, {an.direction})",
            sources=[an.id],
        )
        for an in ctx.anomalies[:2]
    ]
    if ctx.graphNodes:  # Step 15: cite the topology the runbook choice rests on
        # second claim, after the root alarm, so the 5-claim cap never drops it
        evidence.insert(
            1,
            Claim(
                text="Topology context (Graph RAG): " + ", ".join(ctx.graphNodes[:5]),
                sources=ctx.graphNodes[:5],
            ),
        )
    steps = [
        Step(text=f"Follow {r.title} — {r.section}", runbookId=r.runbookId, section=r.section)
        for r in ctx.runbooks[:3]
    ]
    if not steps:
        # Step requires a runbook id; with no runbooks we cannot cite one, so say so in evidence.
        evidence = evidence[:4] + [
            Claim(text="No runbook found; escalate per standard procedure", sources=[root.id])
        ]
    cause = f"Likely {fault_type.replace('_', ' ')}: {root.specificProblem} at {root.siteId}"
    return Answer(
        suspectedCause=cause[:300],
        faultType=fault_type,
        confidence=float(fault.get("confidence", 0.3)),
        evidence=evidence[:5],
        steps=steps,
    )


def _raise_if_alarm_tool_failed(upstream: ToolRecorder) -> None:
    """An empty alarm list is only "no evidence" if the alarm tool itself succeeded."""
    name = upstream.TOOL_NAMES["alarms_for_site"]
    if all(c.get("ok", True) for c in upstream.tool_calls if c.get("name") == name):
        return
    warnings = "; ".join(upstream.warnings) or "alarm tool failed"
    unreachable = any("unavailable" in w for w in upstream.warnings)
    raise UpstreamError(503 if unreachable else 502, f"evidence tools failed: {warnings}"[:300])


async def analyze(
    req: AnalyzeRequest, upstream: ToolRecorder, llm: LLM, max_attempts: int = 3
) -> AnalyzeResponse:
    started = time.perf_counter()
    ctx, _ = await gather(upstream, req)
    if not ctx.alarms:
        _raise_if_alarm_tool_failed(upstream)
        raise NoEvidence()

    errors: list[str] = []
    last_errors: list[str] | None = None
    answer: Answer | None = None
    attempts = 0
    for _ in range(max_attempts):
        attempts += 1
        try:
            raw = await llm.complete(build_messages(ctx, last_errors), ANSWER_SCHEMA)
            answer = validate_answer(raw, ctx)
            break
        except AnswerInvalid as exc:
            last_errors = exc.messages
            errors.append(f"attempt {attempts}: " + "; ".join(exc.messages))
        except LLMError as exc:
            errors.append(f"attempt {attempts}: {exc}")
            break  # LLM is down: don't hammer it, fall back now

    generated_by = "llm" if answer is not None else "fallback"
    if answer is None:
        answer = fallback_answer(ctx)
    return AnalyzeResponse(
        siteId=req.site_id,
        window=req.window,
        answer=answer,
        generatedBy=generated_by,
        model=llm.name if generated_by == "llm" else None,
        attempts=attempts,
        errors=errors,
        context=ctx,
        sourceIds=sorted(ctx.source_ids()),
        warnings=list(upstream.warnings),
        toolCalls=list(upstream.tool_calls),
        durationMs=int((time.perf_counter() - started) * 1000),
    )
