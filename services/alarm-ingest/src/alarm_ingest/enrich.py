from __future__ import annotations

from typing import Any

from netgen import Topology


class Enricher:
    """Enrich alarms with topology information."""

    def __init__(self, topology: Topology) -> None:
        self._topology = topology
        # Build inverse mapping of children -> parent
        self._parent_by_child: dict[str, str] = {}
        for parent, children in topology.children.items():
            for child in children:
                self._parent_by_child[child] = parent

    def enrich(self, alarm: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of alarm with enrichment dict added."""
        site_id = alarm.get("siteId")
        site = self._topology.site_by_id.get(site_id) if site_id else None

        if site is not None:
            # Collect unique node kinds at this site
            node_kinds = sorted({node.kind for node in site.nodes})
            enrichment = {
                "siteName": site.name,
                "region": site.region,
                "siteKind": site.kind,
                "nodeTypes": node_kinds,
                "parentSiteId": self._parent_by_child.get(site.site_id),
                "known": True,
            }
        else:
            enrichment = {
                "siteName": None,
                "region": "Unknown",
                "siteKind": None,
                "nodeTypes": [],
                "parentSiteId": None,
                "known": False,
            }

        enriched = dict(alarm)
        enriched["enrichment"] = enrichment
        return enriched
