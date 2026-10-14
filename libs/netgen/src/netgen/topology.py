"""Topology data structures and deterministic builder."""

from __future__ import annotations

import math
import random
import zlib
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Node:
    """Network node within a site."""

    node_id: str
    kind: Literal["gNB", "eNB", "router"]
    cells: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Site:
    """Network site."""

    site_id: str
    name: str
    region: Literal["North", "Central", "South"]
    kind: Literal["core", "hub", "access"]
    lat: float
    lon: float
    nodes: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Link:
    """Network link between two sites."""

    link_id: str
    a: str
    b: str
    kind: Literal["fibre", "microwave"]
    role: Literal["core", "ring", "access"]


@dataclass(frozen=True, slots=True)
class Topology:
    """Complete network topology."""

    sites: tuple[Site, ...]
    links: tuple[Link, ...]
    site_by_id: dict[str, Site]
    children: dict[str, list[str]]  # parent -> list of child site_ids
    seed: int
    small: bool

    def to_dict(self) -> dict:
        """Return JSON-ready dict with stable ordering."""
        regions = ["North", "Central", "South"]
        return {
            "seed": self.seed,
            "small": self.small,
            "regions": regions,
            "sites": [
                {
                    "siteId": s.site_id,
                    "name": s.name,
                    "region": s.region,
                    "kind": s.kind,
                    "lat": s.lat,
                    "lon": s.lon,
                    "nodes": [
                        {
                            "nodeId": n.node_id,
                            "kind": n.kind,
                            "cells": list(n.cells),
                        }
                        for n in s.nodes
                    ],
                }
                for s in self.sites
            ],
            "links": [
                {
                    "linkId": lk.link_id,
                    "a": lk.a,
                    "b": lk.b,
                    "kind": lk.kind,
                    "role": lk.role,
                }
                for lk in self.links
            ],
            "counts": {
                "regions": len(regions),
                "sites": len(self.sites),
                "nodes": sum(len(s.nodes) for s in self.sites),
                "cells": sum(len(n.cells) for s in self.sites for n in s.nodes),
                "links": len(self.links),
            },
        }


def _stable_seed(base_seed: int, *parts: str) -> int:
    """Generate a stable seed from base seed and string parts using CRC32."""
    key = f"{base_seed}:{':'.join(parts)}"
    return zlib.crc32(key.encode()) & 0xFFFFFFFF


# Region bands stacked north -> south (synthetic coordinates, not real places)
_REGION_BANDS: dict[str, tuple[float, float]] = {
    "North": (24.0, 28.0),
    "Central": (18.0, 24.0),
    "South": (12.0, 18.0),
}


def _create_nodes_and_cells(
    rng: random.Random, site_id: str, kind: Literal["core", "hub", "access"], small: bool
) -> tuple[Node, ...]:
    """Create nodes and cells for a site."""
    if small:
        n_nodes = 1 if kind == "access" else 2
    else:
        n_nodes = rng.randint(2, 4) if kind == "access" else 3

    node_kinds = ["gNB", "eNB", "router"]
    nodes = []
    for i in range(n_nodes):
        node_id = f"{site_id}-N{i + 1}"
        node_kind = rng.choice(node_kinds)
        n_cells = 3
        cells = tuple(f"{node_id}-C{j + 1}" for j in range(n_cells))
        nodes.append(Node(node_id=node_id, kind=node_kind, cells=cells))
    return tuple(nodes)


def build_topology(seed: int = 42, small: bool = True) -> Topology:
    """Build a deterministic realistic telecom topology.

    Args:
        seed: Random seed for reproducibility.
        small: If True, build small topology (12 sites). If False, full (60 sites).

    Returns:
        Topology with sites, links, and hierarchy.
    """
    rng = random.Random(seed)
    regions: list[Literal["North", "Central", "South"]] = ["North", "Central", "South"]

    if small:
        n_core = 2
        n_hubs_per_region = 1
        n_access_total = 7
    else:
        n_core = 2
        n_hubs_per_region = 3
        n_access_total = 60 - n_core - n_hubs_per_region * len(regions)  # 49

    sites: list[Site] = []
    site_idx = 0
    core_ids: list[str] = []
    hub_ids: list[str] = []
    access_ids: list[str] = []
    children: dict[str, list[str]] = {}

    # Create core sites
    for i in range(n_core):
        site_id = f"SITE-{site_idx + 1:03d}"
        name = f"Core-{i + 1}"
        region = regions[i % len(regions)]  # Distribute cores across regions
        # Cores sit in the middle of the map, side by side
        lat, lon = 20.0, 78.0 + 4.0 * i - 2.0 * (n_core - 1)
        nodes = _create_nodes_and_cells(rng, site_id, "core", small)
        site = Site(
            site_id=site_id, name=name, region=region, kind="core", lat=lat, lon=lon, nodes=nodes
        )
        sites.append(site)
        core_ids.append(site_id)
        children[site_id] = []
        site_idx += 1

    # Create hub sites per region (on transport ring)
    for region_idx, region in enumerate(regions):
        for hub_idx in range(n_hubs_per_region):
            site_id = f"SITE-{site_idx + 1:03d}"
            name = f"{region}-Hub-{hub_idx + 1}"
            # Hubs: middle of their region band, spread west -> east
            band_lo, band_hi = _REGION_BANDS[region]
            lat = (band_lo + band_hi) / 2
            lon = 73.0 + 14.0 * (hub_idx + 0.5) / n_hubs_per_region
            if n_hubs_per_region == 1:
                lon = 74.0 + 4.0 * region_idx
            nodes = _create_nodes_and_cells(rng, site_id, "hub", small)
            site = Site(
                site_id=site_id, name=name, region=region, kind="hub", lat=lat, lon=lon, nodes=nodes
            )
            sites.append(site)
            hub_ids.append(site_id)
            children[site_id] = []
            site_idx += 1

    # Create access sites, each homed to one hub
    access_per_hub = n_access_total // len(hub_ids)
    extra = n_access_total % len(hub_ids)
    access_idx = 0
    for hub_idx, hub_id in enumerate(hub_ids):
        hub_site = next(s for s in sites if s.site_id == hub_id)
        hub_region = hub_site.region
        count = access_per_hub + (1 if hub_idx < extra else 0)
        for k in range(count):
            site_id = f"SITE-{site_idx + 1:03d}"
            name = f"{hub_region}-Access-{access_idx + 1}"
            # Access sites fan out on a small circle around their hub (plus tiny jitter)
            angle = 2 * math.pi * (k + 0.5) / max(count, 1)
            lat = round(hub_site.lat + 1.3 * math.sin(angle) + rng.uniform(-0.1, 0.1), 6)
            lon = round(hub_site.lon + 1.6 * math.cos(angle) + rng.uniform(-0.1, 0.1), 6)
            nodes = _create_nodes_and_cells(rng, site_id, "access", small)
            site = Site(
                site_id=site_id,
                name=name,
                region=hub_region,
                kind="access",
                lat=lat,
                lon=lon,
                nodes=nodes,
            )
            sites.append(site)
            access_ids.append(site_id)
            children[site_id] = []
            children[hub_id].append(site_id)
            site_idx += 1
            access_idx += 1

    # Build links
    links: list[Link] = []
    link_idx = 0

    # Core <-> Core links (core role, fibre)
    for i in range(len(core_ids) - 1):
        link_id = f"LNK-{link_idx + 1:03d}"
        links.append(
            Link(link_id=link_id, a=core_ids[i], b=core_ids[i + 1], kind="fibre", role="core")
        )
        link_idx += 1

    # Core -> Hub links (core role, fibre) - each hub connects to both cores
    for hub_id in hub_ids:
        for core_id in core_ids:
            link_id = f"LNK-{link_idx + 1:03d}"
            links.append(Link(link_id=link_id, a=core_id, b=hub_id, kind="fibre", role="core"))
            children[core_id].append(hub_id)
            link_idx += 1

    # Hub ring links per region (ring role, fibre)
    for region in regions:
        region_hubs = [
            h for h in hub_ids if next(s for s in sites if s.site_id == h).region == region
        ]
        if len(region_hubs) > 1:
            for i in range(len(region_hubs)):
                a = region_hubs[i]
                b = region_hubs[(i + 1) % len(region_hubs)]
                link_id = f"LNK-{link_idx + 1:03d}"
                links.append(Link(link_id=link_id, a=a, b=b, kind="fibre", role="ring"))
                link_idx += 1

    # Hub -> Access links (access role, fibre or microwave)
    for hub_id in hub_ids:
        for access_id in children[hub_id]:
            link_id = f"LNK-{link_idx + 1:03d}"
            # Use microwave for some access links for variety
            link_kind = "microwave" if rng.random() < 0.2 else "fibre"
            links.append(
                Link(link_id=link_id, a=hub_id, b=access_id, kind=link_kind, role="access")
            )
            link_idx += 1

    site_by_id = {s.site_id: s for s in sites}

    return Topology(
        sites=tuple(sites),
        links=tuple(links),
        site_by_id=site_by_id,
        children=children,
        seed=seed,
        small=small,
    )
