"""Optional Langfuse export of a run's trace (W17), over Langfuse's public ingestion API.

Off unless LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set (e.g. a
self-hosted Langfuse). No SDK dependency; failures never break a run. The console trace view
works without it: every run keeps its own per-agent trace.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)
transport: httpx.AsyncBaseTransport | None = None  # tests swap this


def enabled() -> bool:
    return all(
        os.getenv(k) for k in ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    )


def events(run: dict[str, Any], sent: int) -> list[dict[str, Any]]:
    """Langfuse ingestion events: one trace per run, one span per new agent step."""
    out = [
        {
            "id": str(uuid.uuid4()),
            "type": "trace-create",
            "timestamp": run["updatedAt"],
            "body": {
                "id": run["runId"],
                "name": "copilot-run",
                "metadata": {"siteId": run["siteId"], "incidentId": run["incidentId"]},
                "tags": ["netsentinel", "w17", run["status"]],
            },
        }
    ]
    for step in run["trace"][sent:]:
        out.append(
            {
                "id": str(uuid.uuid4()),
                "type": "span-create",
                "timestamp": step["startedAt"],
                "body": {
                    "id": f"{run['runId']}-{step['seq']}",
                    "traceId": run["runId"],
                    "name": f"{step['agent']}: {step['name']}",
                    "startTime": step["startedAt"],
                    "metadata": {"durationMs": step["durationMs"], "toolCalls": step["toolCalls"]},
                    "level": "DEFAULT" if step["ok"] else "ERROR",
                    "statusMessage": step["detail"],
                },
            }
        )
    return out


async def export(run: dict[str, Any], sent: int) -> bool:
    if not enabled():
        return False
    host = os.environ["LANGFUSE_HOST"].rstrip("/")
    auth = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
    try:
        async with httpx.AsyncClient(timeout=5.0, transport=transport) as c:
            r = await c.post(
                f"{host}/api/public/ingestion", json={"batch": events(run, sent)}, auth=auth
            )
        return r.status_code < 300
    except httpx.HTTPError as exc:
        logger.warning("langfuse export failed: %s", type(exc).__name__)
        return False
