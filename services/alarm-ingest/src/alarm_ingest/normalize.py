from __future__ import annotations

import datetime as dt
from typing import Any


class InvalidAlarm(ValueError):
    """Raised when an alarm cannot be normalized."""


_SEVERITY_ALIASES = {
    "crit": "critical",
    "critical": "critical",
    "maj": "major",
    "major": "major",
    "min": "minor",
    "minor": "minor",
    "warn": "warning",
    "warning": "warning",
    "clear": "cleared",
    "cleared": "cleared",
    "indeterminate": "warning",
}


def _parse_iso_time(value: str) -> dt.datetime:
    """Parse ISO 8601 string, accept 'Z' suffix, return UTC datetime."""
    # Replace Z with +00:00 for fromisoformat (Python 3.11+ handles Z)
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidAlarm(f"Invalid alarmRaisedTime: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    else:
        parsed = parsed.astimezone(dt.UTC)
    return parsed


def _format_utc_z(dt_val: dt.datetime) -> str:
    """Format datetime as UTC with 'Z' suffix."""
    if dt_val.tzinfo is None:
        dt_val = dt_val.replace(tzinfo=dt.UTC)
    else:
        dt_val = dt_val.astimezone(dt.UTC)
    return dt_val.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw alarm dict, returning a new dict."""
    if not isinstance(raw, dict):
        raise InvalidAlarm("Alarm must be a dict")

    # Required fields
    alarm_id = raw.get("id")
    if not isinstance(alarm_id, str) or not alarm_id:
        raise InvalidAlarm("Missing or invalid 'id'")

    alarmed_obj = raw.get("alarmedObject")
    site_id = raw.get("siteId")
    if isinstance(alarmed_obj, dict):
        obj_id = alarmed_obj.get("id")
        if isinstance(obj_id, str) and obj_id:
            site_id = obj_id
    if not isinstance(site_id, str) or not site_id:
        raise InvalidAlarm("Missing siteId (or alarmedObject.id)")

    severity_raw = raw.get("perceivedSeverity")
    if not isinstance(severity_raw, str):
        raise InvalidAlarm("Missing perceivedSeverity")
    severity_lower = severity_raw.lower()
    severity = _SEVERITY_ALIASES.get(severity_lower)
    if severity is None:
        raise InvalidAlarm(f"Unknown severity: {severity_raw}")

    # alarmRaisedTime
    raised_time_raw = raw.get("alarmRaisedTime")
    if isinstance(raised_time_raw, str) and raised_time_raw:
        try:
            raised_dt = _parse_iso_time(raised_time_raw)
        except InvalidAlarm:
            raise
    else:
        raised_dt = dt.datetime.now(dt.UTC)

    # state
    state_raw = raw.get("state")
    if severity == "cleared":
        state = "cleared"
    elif isinstance(state_raw, str) and state_raw in ("raised", "cleared"):
        state = state_raw
    else:
        state = "raised"

    # Build normalized alarm
    normalized = {
        "id": alarm_id,
        "href": raw.get("href") or f"/alarm/{alarm_id}",
        "alarmType": raw.get("alarmType") or "communicationsAlarm",
        "perceivedSeverity": severity,
        "probableCause": raw.get("probableCause") or "unknown",
        "specificProblem": raw.get("specificProblem") or "",
        "alarmedObject": {
            "id": site_id,
            "@referredType": (
                alarmed_obj.get("@referredType") if isinstance(alarmed_obj, dict) else None
            )
            or "Site",
        },
        "siteId": site_id,
        "alarmRaisedTime": _format_utc_z(raised_dt),
        "state": state,
        "sourceSystemId": raw.get("sourceSystemId") or "unknown",
        "@type": raw.get("@type") or "Alarm",
    }
    return normalized
