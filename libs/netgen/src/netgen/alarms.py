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

    # Pick a link to cut: prefer a hub's uplink (ring or core link where b is a hub)
    # or an access link
    candidate_links = []
    hub_uplinks = []
    for lnk in topology.links:
        site_b = topology.site_by_id[lnk.b]
        if site_b.kind == "hub" and lnk.role in ("ring", "core"):
            hub_uplinks.append((lnk, "hub_uplink"))
        elif site_b.kind == "access" and lnk.role == "access":
            candidate_links.append((lnk, "access"))

    # If we have hub uplinks, choose among them; otherwise use access links
    chosen_link, cut_type = rng.choice(hub_uplinks or candidate_links)

    if not chosen_link:
        # Fallback to any fibre link
        fibre_links = [lnk for lnk in topology.links if lnk.kind == "fibre"]
        if not fibre_links:
            return []
        chosen_link, cut_type = rng.choice([(lnk, "fallback") for lnk in fibre_links])

    site_a = chosen_link.a
    site_b = chosen_link.b

    # Determine downstream access sites from the far side (b)
    def get_downstream_access(site_id: str) -> list[str]:
        access_sites: list[str] = []
        stack = [site_id]
        while stack:
            current = stack.pop()
            for child in topology.children.get(current, []):
                child_site = topology.site_by_id[child]
                if child_site.kind == "access":
                    access_sites.append(child)
                else:
                    stack.append(child)
        return access_sites

    downstream_access = get_downstream_access(site_b)
    if not downstream_access and topology.site_by_id[site_b].kind == "access":
        downstream_access = [site_b]

    alarms: list[tuple[float, dict[str, Any]]] = []
    base_time = start.replace(microsecond=0)

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

    # 2. Sympathetic alarms on downstream access sites over ~120 seconds
    sympathetic_alarms = [
        ("major", "S1 link down", "transportAlarm"),
        ("major", "Cell unavailable", "equipmentAlarm"),
        ("minor", "High BLER", "qualityOfServiceAlarm"),
        ("warning", "Degraded throughput", "qualityOfServiceAlarm"),
    ]

    for idx, (severity, problem, a_type) in enumerate(sympathetic_alarms):
        for access_id in downstream_access:
            offset = 5.0 + idx * 30.0 + rng.uniform(0, 2)
            alarm_time = base_time + timedelta(seconds=offset)
            alarm = make_alarm(
                rng=rng,
                alarm_type=a_type,
                perceived_severity=severity,
                probable_cause="underlyingResourceUnavailable",
                specific_problem=problem,
                alarmed_object_id=access_id,
                site_id=access_id,
                alarm_raised_time=alarm_time,
            )
            alarms.append((offset, alarm))

    # 3. Cleared alarms at the end (~120s)
    clear_offset = 120.0 + rng.uniform(0, 5)
    clear_time = base_time + timedelta(seconds=clear_offset)

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
    for access_id in downstream_access:
        alarm = make_alarm(
            rng=rng,
            alarm_type="communicationsAlarm",
            perceived_severity="cleared",
            probable_cause="underlyingResourceUnavailable",
            specific_problem="Service restored",
            alarmed_object_id=access_id,
            site_id=access_id,
            state="cleared",
            alarm_raised_time=clear_time + timedelta(seconds=rng.uniform(0, 2)),
        )
        alarms.append((clear_offset + rng.uniform(0, 2), alarm))

    # Sort by offset
    alarms.sort(key=lambda x: x[0])
    return alarms
