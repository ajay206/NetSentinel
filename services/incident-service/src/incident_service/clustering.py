"""Topology-aware alarm clustering (W13).

An alarm joins an *active* incident when its site is related to a member site: the same site,
an ancestor or descendant within ``max_hops`` in the topology tree, the other end of a direct
link (both ends of a cut fibre), or a sibling under a shared non-core ancestor within
``max_hops`` (sympathetic alarms behind one hub). An incident is active while it saw an alarm
within ``gap_seconds`` of this one, in event time (session window). Incidents that become
connected are merged; the root is the member site closest to the core. Cleared alarms only
update incidents. Deterministic: ids come from the first alarm id and ``replay`` sorts input.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

SEVERITY_RANK: Mapping[str, int] = {
    "critical": 0,
    "major": 1,
    "minor": 2,
    "warning": 3,
    "indeterminate": 4,
    "cleared": 9,
}


class TopologyLike(Protocol):
    site_by_id: Mapping[str, Any]
    children: Mapping[str, list[str]]


def _parse_iso(ts: Any) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rank(severity: str) -> int:
    return SEVERITY_RANK.get(severity, 5)


@dataclass(eq=False)
class Incident:
    id: str
    root_site_id: str
    first_seen: datetime
    last_seen: datetime
    site_ids: set[str] = field(default_factory=set)
    alarm_ids: list[str] = field(default_factory=list)
    alarm_keys: list[str] = field(default_factory=list)
    severity: str = "cleared"
    region: str | None = None
    status: str = "open"
    cleared_sites: set[str] = field(default_factory=set)
    version: int = 0
    # per-site (worst severity rank, first raised time) for root selection
    site_info: dict[str, tuple[int, datetime]] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rootSiteId": self.root_site_id,
            "siteIds": sorted(self.site_ids),
            "alarmIds": list(self.alarm_ids),
            "alarmKeys": list(self.alarm_keys),
            "alarmCount": len(self.alarm_ids),
            "severity": self.severity,
            "region": self.region,
            "firstSeen": _iso_z(self.first_seen),
            "lastSeen": _iso_z(self.last_seen),
            "status": self.status,
            "version": self.version,
        }


class IncidentClusterer:
    def __init__(self, topology: TopologyLike, gap_seconds: int = 300, max_hops: int = 4) -> None:
        self.topology = topology
        self.gap = timedelta(seconds=gap_seconds)
        self.max_hops = max_hops
        self.incidents: dict[str, Incident] = {}
        self._alarm_incident: dict[str, str] = {}
        self.parent: dict[str, str] = {
            child: parent for parent, kids in topology.children.items() for child in kids
        }
        self.alarms_seen = 0
        self.neighbours: dict[str, set[str]] = {}
        for link in getattr(topology, "links", ()):
            self.neighbours.setdefault(link.a, set()).add(link.b)
            self.neighbours.setdefault(link.b, set()).add(link.a)

    # -- topology helpers ---------------------------------------------------------------
    def _ancestors(self, site_id: str, limit: int | None = None) -> list[str]:
        out: list[str] = []
        cur = site_id
        while cur in self.parent and (limit is None or len(out) < limit):
            cur = self.parent[cur]
            out.append(cur)
        return out

    def _depth(self, site_id: str) -> int:
        return len(self._ancestors(site_id))

    def _is_core(self, site_id: str) -> bool:
        return getattr(self.topology.site_by_id.get(site_id), "kind", None) == "core"

    def _related(self, site_id: str, inc: Incident) -> bool:
        if site_id in inc.site_ids:
            return True
        if self.neighbours.get(site_id, set()) & inc.site_ids:
            return True
        mine = self._ancestors(site_id, self.max_hops)
        if any(a in inc.site_ids for a in mine):
            return True
        shared = {a for a in mine if not self._is_core(a)}
        for other in inc.site_ids:
            theirs = self._ancestors(other, self.max_hops)
            if site_id in theirs or shared.intersection(theirs):
                return True
        return False

    def _active(self, t: datetime) -> list[Incident]:
        return [
            inc
            for inc in self.incidents.values()
            if inc.status == "open" and abs(t - inc.last_seen) <= self.gap
        ]

    def _update_root(self, inc: Incident) -> None:
        def key(sid: str) -> tuple[int, int, datetime, str]:
            rank, first = inc.site_info[sid]
            return (self._depth(sid), rank, first, sid)

        inc.root_site_id = min(inc.site_ids, key=key)
        site = self.topology.site_by_id.get(inc.root_site_id)
        inc.region = getattr(site, "region", None) or inc.region

    @staticmethod
    def _add_alarm(inc: Incident, alarm_id: str, key: str | None, t: datetime) -> None:
        inc.alarm_ids.append(alarm_id)
        if key and key not in inc.alarm_keys:
            inc.alarm_keys.append(key)
        inc.first_seen = min(inc.first_seen, t)
        inc.last_seen = max(inc.last_seen, t)
        inc.version += 1

    # -- public API ---------------------------------------------------------------------
    def add(self, alarm: Mapping[str, Any]) -> Incident | None:
        """Add one alarm; returns the incident it changed, or None if ignored."""
        obj = alarm.get("alarmedObject") or {}
        site_id = alarm.get("siteId") or (obj.get("id") if isinstance(obj, Mapping) else None)
        alarm_id = alarm.get("id")
        t = _parse_iso(alarm.get("alarmRaisedTime"))
        if not site_id or not alarm_id or t is None or alarm_id in self._alarm_incident:
            return None
        self.alarms_seen += 1
        severity = str(alarm.get("perceivedSeverity") or "").lower()
        dedup = alarm.get("dedup") or {}
        key = dedup.get("key") if isinstance(dedup, Mapping) else None
        cleared = severity == "cleared" or str(alarm.get("state") or "").lower() == "cleared"
        active = self._active(t)

        if cleared:
            for inc in sorted(active, key=lambda i: (i.first_seen, i.id)):
                if site_id in inc.site_ids:
                    self._add_alarm(inc, alarm_id, key, t)
                    inc.cleared_sites.add(site_id)
                    if inc.cleared_sites >= inc.site_ids:
                        inc.status = "cleared"
                    self._alarm_incident[alarm_id] = inc.id
                    return inc
            return None

        candidates = sorted(
            (inc for inc in active if self._related(site_id, inc)),
            key=lambda i: (i.first_seen, i.id),
        )
        if candidates:
            target, others = candidates[0], candidates[1:]
            for other in others:  # merge connected incidents into the oldest
                target.site_ids |= other.site_ids
                target.cleared_sites |= other.cleared_sites
                for aid in other.alarm_ids:
                    target.alarm_ids.append(aid)
                    self._alarm_incident[aid] = target.id
                for k in other.alarm_keys:
                    if k not in target.alarm_keys:
                        target.alarm_keys.append(k)
                for sid, (rank, first) in other.site_info.items():
                    old = target.site_info.get(sid)
                    target.site_info[sid] = (
                        (rank, first) if old is None else (min(old[0], rank), min(old[1], first))
                    )
                if _rank(other.severity) < _rank(target.severity):
                    target.severity = other.severity
                target.first_seen = min(target.first_seen, other.first_seen)
                target.last_seen = max(target.last_seen, other.last_seen)
                del self.incidents[other.id]
        else:
            target = Incident(
                id="INC-" + uuid.uuid5(uuid.NAMESPACE_URL, str(alarm_id)).hex[:10].upper(),
                root_site_id=site_id,
                first_seen=t,
                last_seen=t,
                severity=severity or "indeterminate",
            )
            self.incidents[target.id] = target

        self._add_alarm(target, alarm_id, key, t)
        target.site_ids.add(site_id)
        target.cleared_sites.discard(site_id)
        target.status = "open"
        if _rank(severity) < _rank(target.severity):
            target.severity = severity
        old = target.site_info.get(site_id)
        rank = _rank(severity)
        target.site_info[site_id] = (
            (rank, t) if old is None else (min(old[0], rank), min(old[1], t))
        )
        self._alarm_incident[alarm_id] = target.id
        self._update_root(target)
        return target

    def snapshot(self) -> list[dict[str, Any]]:
        """All incidents, most recently active first."""
        ordered = sorted(self.incidents.values(), key=lambda i: (i.last_seen, i.id), reverse=True)
        return [inc.to_dict() for inc in ordered]


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def replay(
    topology: TopologyLike,
    alarms: Iterable[Mapping[str, Any]],
    gap_seconds: int = 300,
    max_hops: int = 4,
) -> list[dict[str, Any]]:
    """Cluster a batch deterministically (input order does not matter)."""
    ordered = sorted(
        alarms,
        key=lambda a: (_parse_iso(a.get("alarmRaisedTime")) or _EPOCH, str(a.get("id", ""))),
    )
    clusterer = IncidentClusterer(topology, gap_seconds, max_hops)
    for alarm in ordered:
        clusterer.add(alarm)
    snap = clusterer.snapshot()
    return sorted(snap, key=lambda d: (d["firstSeen"], d["id"]))


def compression_ratio(alarm_count: int, incident_count: int) -> float:
    return 0.0 if incident_count == 0 else alarm_count / incident_count
