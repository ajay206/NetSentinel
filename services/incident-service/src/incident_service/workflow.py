"""Step 13b: operator workflow on incidents and alarms (acknowledge, assign, resolve, notes).

Kept beside the clusterer as an overlay: clustering stays deterministic on replay, while human
actions are stored here (in memory, bounded) and merged into API responses. Every action is
also audited by the gateway, which is the only caller and enforces the operator role; this
service checks the forwarded role again (defence in depth).
"""

from __future__ import annotations

import re
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

ACTOR_RE = re.compile(r"^[a-z][a-z0-9._-]{2,31}$")
MAX_NOTES = 50
MAX_ALARM_ITEMS = 5000
WRITE_ROLES = ("operator", "admin")


class IncidentAction(BaseModel):
    action: Literal["ack", "assign", "resolve", "note"]
    assignee: str | None = Field(default=None, max_length=32)
    note: str = Field(default="", max_length=1000)


class AlarmAction(BaseModel):
    key: str = Field(..., min_length=1, max_length=400)
    action: Literal["ack", "resolve", "note"]
    note: str = Field(default="", max_length=1000)


class ActionError(ValueError):
    pass


def new_workflow() -> dict[str, Any]:
    return {
        "state": "new",
        "assignee": None,
        "ackedBy": None,
        "ackedAt": None,
        "resolvedBy": None,
        "resolvedAt": None,
        "notes": [],
    }


def apply(
    wf: dict[str, Any],
    action: str,
    actor: str,
    note: str = "",
    assignee: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Apply one action to a workflow record (mutates and returns it)."""
    now = time.time() if now is None else now
    note = note.strip()
    if action == "ack":
        if wf["state"] == "resolved":
            raise ActionError("Already resolved")
        wf.update(state="acknowledged", ackedBy=actor, ackedAt=now)
    elif action == "assign":
        if not assignee or not ACTOR_RE.match(assignee):
            raise ActionError("Assignee must be a valid username")
        wf["assignee"] = assignee
        if wf["state"] == "new":
            wf.update(state="acknowledged", ackedBy=actor, ackedAt=now)
    elif action == "resolve":
        if not note:
            raise ActionError("A resolution note is required")
        wf.update(state="resolved", resolvedBy=actor, resolvedAt=now)
    elif action == "note":
        if not note:
            raise ActionError("Note is empty")
    else:  # pragma: no cover - guarded by the Literal type
        raise ActionError("Unknown action")
    entry = {"ts": now, "by": actor, "action": action, "text": note}
    if assignee and action == "assign":
        entry["assignee"] = assignee
    wf["notes"] = (wf["notes"] + [entry])[-MAX_NOTES:]
    return wf


class WorkflowStore:
    def __init__(self) -> None:
        self.incidents: dict[str, dict[str, Any]] = {}
        self.alarms: dict[str, dict[str, Any]] = {}

    def incident(self, incident_id: str) -> dict[str, Any]:
        return self.incidents.setdefault(incident_id, new_workflow())

    def alarm(self, key: str) -> dict[str, Any]:
        if key not in self.alarms and len(self.alarms) >= MAX_ALARM_ITEMS:
            oldest = min(self.alarms, key=lambda k: self.alarms[k]["notes"][-1]["ts"])
            del self.alarms[oldest]
        return self.alarms.setdefault(key, new_workflow())
