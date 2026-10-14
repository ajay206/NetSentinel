"""Alarm generation following TMF642 and X.733."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from netgen.topology import Topology

SEVERITIES = ("critical", "major", "minor", "warning", "cleared")


def _make_uuid(rng: random.Random) -> str:
    """Generate a UUID from random bits (deterministic with seeded rng)."""
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def make_alarm(
    rng: random.Random,
    alarm_type: str,
    perceived_severity: str,
    probable_cause: str,
    specific_problem: str,
    alarmed_object_id: str,
    alarmed_object_type: str = "Site",
    site_id: str | None = None,
    state: str = "raised",
    source_system_id: str = "netgen-simulator",
    alarm_raised_time: datetime | None = None,
) -> dict[str, Any]:
    """Create a TMF642-like alarm dictionary with camelCase keys."""
    if perceived_severity not in SEVERITIES:
        raise ValueError(f"Invalid severity: {perceived_severity}. Must be one of {SEVERITIES}")

    alarm_id = _make_uuid(rng)
    now = alarm_raised_time or datetime.now(UTC)

    return {
        "id": alarm_id,
        "href": f"/alarm/{alarm_id}",
        "alarmType": alarm_type,
        "perceivedSeverity": perceived_severity,
        "probableCause": probable_cause,
        "specificProblem": specific_problem,
        "alarmedObject": {
            "id": alarmed_object_id,
            "@referredType": alarmed_object_type,
        },
        "siteId": site_id or alarmed_object_id,
        "alarmRaisedTime": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "state": state,
        "sourceSystemId": source_system_id,
        "@type": "Alarm",
    }


def fibre_cut(
    topology: Topology,
    seed: int,
    start: datetime,
) -> list[tuple[float, dict[str, Any]]]:
    """Generate a deterministic fibre cut alarm scenario.

    Args:
        topology: Network topology.
        seed: Random seed for reproducibility.
        start: Scenario start time (UTC).

    Returns:
        List of (offset_seconds, alarm_dict) tuples.
    """
    rng = random.Random(seed)

    # Pick a fibre link deterministically
    fibre_links = [lnk for lnk in topology.links if lnk.kind == "fibre"]
    if not fibre_links:
        return []

    # Prefer an aggregation uplink so the cut takes several cells down (a visible storm)
    uplinks = [lnk for lnk in fibre_links if topology.site_by_id[lnk.b].kind == "agg"]
    cut_link = rng.choice(uplinks or fibre_links)
    site_a = cut_link.a
    site_b = cut_link.b

    # Determine downstream cells from both ends
    def get_downstream_cells(site_id: str) -> list[str]:
        cells: list[str] = []
        stack = [site_id]
        while stack:
            current = stack.pop()
            for child in topology.children.get(current, []):
                child_site = topology.site_by_id[child]
                if child_site.kind == "cell":
                    cells.append(child)
                else:
                    stack.append(child)
        return cells

    # Only the far side (b) of the cut loses service; core-core cuts have no cells behind them
    far_side = topology.site_by_id[site_b]
    all_downstream = [site_b] if far_side.kind == "cell" else []
    if far_side.kind == "agg":
        all_downstream = get_downstream_cells(site_b)

    alarms: list[tuple[float, dict[str, Any]]] = []
    base_time = start

    # 1. Critical LOS on both ends of the cut link (simultaneous)
    for site_id in (site_a, site_b):
        alarm = make_alarm(
            rng=rng,
            alarm_type="communicationsAlarm",
            perceived_severity="critical",
            probable_cause="lossOfSignal",
            specific_problem="LOS",
            alarmed_object_id=site_id,
            site_id=site_id,
            alarm_raised_time=base_time,
        )
        alarms.append((0.0, alarm))

    # 2. Sympathetic alarms on downstream cells over ~120 seconds
    sympathetic_alarms = [
        ("major", "S1 link down", "transportAlarm"),
        ("major", "Cell unavailable", "equipmentAlarm"),
        ("minor", "High BLER", "qualityOfServiceAlarm"),
        ("warning", "Degraded throughput", "qualityOfServiceAlarm"),
    ]

    for idx, (severity, problem, a_type) in enumerate(sympathetic_alarms):
        for cell_id in all_downstream:
            offset = 5.0 + idx * 30.0 + rng.uniform(0, 2)
            alarm_time = base_time.replace(microsecond=0)
            # Add offset seconds

            alarm_time = alarm_time + timedelta(seconds=offset)
            alarm = make_alarm(
                rng=rng,
                alarm_type=a_type,
                perceived_severity=severity,
                probable_cause="underlyingResourceUnavailable",
                specific_problem=problem,
                alarmed_object_id=cell_id,
                site_id=cell_id,
                alarm_raised_time=alarm_time,
            )
            alarms.append((offset, alarm))

    # 3. Cleared alarms at the end (~120s)
    clear_offset = 120.0 + rng.uniform(0, 5)
    clear_time = base_time.replace(microsecond=0)

    clear_time = clear_time + timedelta(seconds=clear_offset)

    # Clear the original LOS alarms
    for site_id in (site_a, site_b):
        alarm = make_alarm(
            rng=rng,
            alarm_type="communicationsAlarm",
            perceived_severity="cleared",
            probable_cause="lossOfSignal",
            specific_problem="LOS cleared",
            alarmed_object_id=site_id,
            site_id=site_id,
            state="cleared",
            alarm_raised_time=clear_time,
        )
        alarms.append((clear_offset, alarm))

    # Clear sympathetic alarms
    for cell_id in all_downstream:
        alarm = make_alarm(
            rng=rng,
            alarm_type="communicationsAlarm",
            perceived_severity="cleared",
            probable_cause="underlyingResourceUnavailable",
            specific_problem="Service restored",
            alarmed_object_id=cell_id,
            site_id=cell_id,
            state="cleared",
            alarm_raised_time=clear_time,
        )
        alarms.append((clear_offset + rng.uniform(0, 2), alarm))

    # Sort by offset
    alarms.sort(key=lambda x: x[0])
    return alarms
