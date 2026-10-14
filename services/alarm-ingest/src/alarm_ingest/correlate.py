from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from netgen import Topology


class Correlator:
    """Basic root-cause correlation grouping."""

    def __init__(
        self,
        topology: Topology,
        window_seconds: float = 180.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._topology = topology
        self._window = window_seconds
        self._clock = clock
        # group_id -> (root_site_id, start_time_monotonic)
        self._groups: dict[str, tuple[str, float]] = {}
        # Precompute descendants for each site (including self)
        self._descendants: dict[str, set[str]] = {}
        for site_id in topology.site_by_id:
            self._descendants[site_id] = self._get_descendants(site_id)

    def _get_descendants(self, site_id: str) -> set[str]:
        """Return set of site_id and all its descendants."""
        result = {site_id}
        stack = [site_id]
        while stack:
            current = stack.pop()
            for child in self._topology.children.get(current, []):
                if child not in result:
                    result.add(child)
                    stack.append(child)
        return result

    def _prune_expired(self, now: float) -> None:
        expired = [gid for gid, (_, ts) in self._groups.items() if now - ts > self._window]
        for gid in expired:
            del self._groups[gid]

    def correlate(self, alarm: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of alarm with correlation info added."""
        now = self._clock()
        self._prune_expired(now)

        site_id = alarm.get("siteId")
        severity = alarm.get("perceivedSeverity")
        alarm_id = alarm.get("id", "")

        correlation = {"groupId": None, "rootSiteId": None, "role": "none"}

        if severity == "critical" and site_id:
            # Open a new group for this root alarm
            # A repeated (flapping) critical at the same root re-uses its open group
            existing = [gid for gid, (root, _) in self._groups.items() if root == site_id]
            group_id = existing[0] if existing else f"corr-{alarm_id}"
            self._groups[group_id] = (site_id, now)
            correlation = {"groupId": group_id, "rootSiteId": site_id, "role": "root"}
        elif site_id:
            # Find matching groups where site_id is in descendants of root
            matching_groups = []
            for gid, (root_site, start_ts) in self._groups.items():
                if site_id in self._descendants.get(root_site, set()):
                    matching_groups.append((gid, root_site, start_ts))
            if matching_groups:
                # Use most recent group (by start_ts)
                matching_groups.sort(key=lambda x: x[2], reverse=True)
                gid, root_site, _ = matching_groups[0]
                correlation = {"groupId": gid, "rootSiteId": root_site, "role": "symptom"}

        result = dict(alarm)
        result["correlation"] = correlation
        return result
