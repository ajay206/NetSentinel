from __future__ import annotations

import json

from copilot_orchestrator.models import Context

SYSTEM_PROMPT = (
    "You are a concise NOC assistant. Answer ONLY with JSON matching the provided schema. "
    "Every evidence claim must cite source IDs copied exactly from the context. "
    "Steps must use runbookIds from the context. Never invent IDs. Be brief."
)


def build_messages(ctx: Context, errors: list[str] | None = None) -> list[dict[str, str]]:
    context_dump = {
        "site_id": ctx.site_id,
        "window_minutes": ctx.window_minutes,
        "alarms": [
            {
                "id": a.id,
                "siteId": a.siteId,
                "specificProblem": a.specificProblem,
                "perceivedSeverity": a.perceivedSeverity,
                "alarmRaisedTime": a.alarmRaisedTime,
                "role": a.role,
            }
            for a in ctx.alarms
        ],
        "anomalies": [
            {
                "id": an.id,
                "cellId": an.cellId,
                "kpi": an.kpi,
                "ts": an.ts,
                "score": an.score,
                "direction": an.direction,
            }
            for an in ctx.anomalies
        ],
        "fault": ctx.fault,
        "runbooks": [
            {
                "runbookId": r.runbookId,
                "title": r.title,
                "section": r.section,
                "snippet": r.snippet,
                "nodeIds": r.nodeIds,
            }
            for r in ctx.runbooks
        ],
        # Step 15: graph node ids (sites / links / cells) are citable sources too
        "graphNodes": ctx.graphNodes,
    }

    user_content = json.dumps(context_dump, separators=(",", ":"))
    if errors:
        user_content += "\n\nYour previous answer was invalid: " + "; ".join(errors) + ". Fix it."

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
