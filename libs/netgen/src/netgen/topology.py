"""Topology data structures and deterministic builder."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Site:
    """Network site."""

    site_id: str
    region: Literal["North", "South", "East", "West"]
    kind: Literal["core", "agg", "cell"]


@dataclass(frozen=True, slots=True)
class Link:
    """Network link between two sites."""

    link_id: str
    a: str
    b: str
    kind: Literal["fibre", "microwave", "satellite"]


@dataclass(frozen=True, slots=True)
class Topology:
    """Complete network topology."""

    sites: list[Site]
    links: list[Link]
    site_by_id: dict[str, Site]
    children: dict[str, list[str]]  # parent -> list of child site_ids


def build_topology(seed: int, n_sites: int = 12) -> Topology:
    """Build a deterministic tree topology: core -> agg -> cell.

    Args:
        seed: Random seed for reproducibility.
        n_sites: Total number of sites (minimum 3).

    Returns:
        Topology with sites and links.
    """
    if n_sites < 3:
        raise ValueError("n_sites must be at least 3")

    rng = random.Random(seed)
    regions = ["North", "South", "East", "West"]

    # Determine counts: at least 1 core, 1 agg, rest cells
    n_core = max(1, n_sites // 6)
    n_agg = max(1, (n_sites - n_core) // 3)
    n_cell = n_sites - n_core - n_agg

    sites: list[Site] = []
    site_idx = 0

    # Create core sites
    core_ids: list[str] = []
    for _ in range(n_core):
        site_id = f"SITE-{site_idx + 1:03d}"
        site = Site(site_id=site_id, region=rng.choice(regions), kind="core")
        sites.append(site)
        core_ids.append(site_id)
        site_idx += 1

    # Create agg sites, each attached to a core
    agg_ids: list[str] = []
    for _ in range(n_agg):
        site_id = f"SITE-{site_idx + 1:03d}"
        site = Site(site_id=site_id, region=rng.choice(regions), kind="agg")
        sites.append(site)
        agg_ids.append(site_id)
        site_idx += 1

    # Create cell sites, each attached to an agg
    cell_ids: list[str] = []
    for _ in range(n_cell):
        site_id = f"SITE-{site_idx + 1:03d}"
        site = Site(site_id=site_id, region=rng.choice(regions), kind="cell")
        sites.append(site)
        cell_ids.append(site_id)
        site_idx += 1

    # Build links: core->agg (fibre), agg->cell (fibre)
    links: list[Link] = []
    link_idx = 0
    children: dict[str, list[str]] = {s.site_id: [] for s in sites}

    # Core -> Core chain (keeps the whole network one tree: n_sites - 1 links)
    for prev_core, next_core in zip(core_ids, core_ids[1:], strict=False):
        link_id = f"LNK-{link_idx + 1:03d}"
        links.append(Link(link_id=link_id, a=prev_core, b=next_core, kind="fibre"))
        link_idx += 1

    # Core -> Agg links
    for agg_id in agg_ids:
        parent_core = core_ids[agg_ids.index(agg_id) % len(core_ids)]
        link_id = f"LNK-{link_idx + 1:03d}"
        links.append(Link(link_id=link_id, a=parent_core, b=agg_id, kind="fibre"))
        children[parent_core].append(agg_id)
        link_idx += 1

    # Agg -> Cell links
    for cell_id in cell_ids:
        parent_agg = agg_ids[cell_ids.index(cell_id) % len(agg_ids)]
        link_id = f"LNK-{link_idx + 1:03d}"
        links.append(Link(link_id=link_id, a=parent_agg, b=cell_id, kind="fibre"))
        children[parent_agg].append(cell_id)
        link_idx += 1

    site_by_id = {s.site_id: s for s in sites}

    return Topology(
        sites=sites,
        links=links,
        site_by_id=site_by_id,
        children=children,
    )
