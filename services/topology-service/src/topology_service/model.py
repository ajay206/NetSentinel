"""Plain-data view of the network loaded into the graph (from netgen or data/topology.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TopoData:
    sites: list[dict[str, Any]]
    links: list[dict[str, Any]]
    # child siteId -> parent siteId (core -> hub -> access homing tree)
    parent: dict[str, str] = field(default_factory=dict)

    @property
    def site_ids(self) -> set[str]:
        return {s["siteId"] for s in self.sites}

    @property
    def node_ids(self) -> set[str]:
        return {n["nodeId"] for s in self.sites for n in s["nodes"]}

    @property
    def link_ids(self) -> set[str]:
        return {link["linkId"] for link in self.links}

    def counts(self) -> dict[str, int]:
        nodes = [n for s in self.sites for n in s["nodes"]]
        return {
            "sites": len(self.sites),
            "nodes": len(nodes),
            "cells": sum(len(n["cells"]) for n in nodes),
            "links": len(self.links),
        }


def derive_parents(sites: list[dict[str, Any]], links: list[dict[str, Any]]) -> dict[str, str]:
    """Homing tree: access -> its hub; hub -> the first core it links to."""
    kind = {s["siteId"]: s["kind"] for s in sites}
    parent: dict[str, str] = {}
    for link in links:
        a, b = link["a"], link["b"]
        if link["role"] == "access":
            hub, acc = (a, b) if kind.get(a) == "hub" else (b, a)
            parent.setdefault(acc, hub)
        elif link["role"] == "core" and {kind.get(a), kind.get(b)} == {"core", "hub"}:
            core, hub = (a, b) if kind.get(a) == "core" else (b, a)
            parent.setdefault(hub, core)
    return parent


def from_dict(d: dict[str, Any]) -> TopoData:
    sites, links = list(d["sites"]), list(d["links"])
    return TopoData(sites=sites, links=links, parent=derive_parents(sites, links))


def load_json(path: str | Path) -> TopoData:
    return from_dict(json.loads(Path(path).read_text()))


def from_netgen(seed: int = 42, small: bool = True) -> TopoData:
    from netgen import build_topology

    return from_dict(build_topology(seed=seed, small=small).to_dict())
