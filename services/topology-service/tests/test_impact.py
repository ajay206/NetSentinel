"""W14: impact semantics on the in-memory graph, checked against an independent brute force."""

from __future__ import annotations

import pytest
from topology_service.graph import MemoryGraph, UnknownTarget
from topology_service.model import TopoData, derive_parents, from_netgen, load_json


def reachable_from_core(topo: TopoData, dead_links: set[str], dead_sites: set[str]) -> set[str]:
    """Independent fixpoint (no BFS queue): grow the reached set until it stops changing."""
    reached = {s["siteId"] for s in topo.sites if s["kind"] == "core"} - dead_sites
    changed = True
    while changed:
        changed = False
        for link in topo.links:
            if link["linkId"] in dead_links or {link["a"], link["b"]} & dead_sites:
                continue
            for x, y in ((link["a"], link["b"]), (link["b"], link["a"])):
                if x in reached and y not in reached:
                    reached.add(y)
                    changed = True
    return reached


@pytest.fixture(params=[True, False], ids=["small", "full"])
def topo(request) -> TopoData:
    return from_netgen(seed=42, small=request.param)


async def _graph(topo: TopoData) -> MemoryGraph:
    g = MemoryGraph()
    await g.load(topo)
    return g


async def test_link_failure_matches_brute_force_for_every_link(topo):
    g = await _graph(topo)
    for link in topo.links:
        res = (await g.impact("link", link["linkId"])).to_dict()
        expected = topo.site_ids - reachable_from_core(topo, {link["linkId"]}, set())
        assert {s["siteId"] for s in res["impactedSites"]} == expected, link["linkId"]
        assert all(s["reason"] == "isolated" for s in res["impactedSites"])


async def test_site_failure_matches_brute_force_for_every_site(topo):
    g = await _graph(topo)
    for site in topo.sites:
        res = (await g.impact("site", site["siteId"])).to_dict()
        isolated = topo.site_ids - reachable_from_core(topo, set(), {site["siteId"]})
        isolated.discard(site["siteId"])
        got = {s["siteId"]: s["reason"] for s in res["impactedSites"]}
        assert got.pop(site["siteId"]) == "failed"
        assert set(got) == isolated and set(got.values()) <= {"isolated"}


async def test_the_build_plan_question_lnk_012():
    """'Which cells lose service if link LNK-012 fails?' (small topology, seed 42)."""
    topo = from_netgen(seed=42, small=True)
    g = await _graph(topo)
    res = (await g.impact("link", "LNK-012")).to_dict()
    link = next(link for link in topo.links if link["linkId"] == "LNK-012")
    assert (link["a"], link["b"], link["role"]) == ("SITE-004", "SITE-010", "access")
    site10 = next(s for s in topo.sites if s["siteId"] == "SITE-010")
    cells = sorted(c for n in site10["nodes"] for c in n["cells"])
    assert res["impactedSites"] == [
        {"siteId": "SITE-010", "kind": "access", "reason": "isolated", "cells": cells}
    ]
    assert res["cellsLost"] == len(cells) and res["sitesIsolated"] == 1
    assert res["elapsedMs"] < 100


async def test_redundant_core_link_loses_nothing():
    g = await _graph(from_netgen(seed=42, small=True))
    res = (await g.impact("link", "LNK-001")).to_dict()  # core <-> core, hubs are dual-homed
    assert res["impactedSites"] == [] and res["cellsLost"] == 0


async def test_node_failure_only_loses_its_cells():
    topo = from_netgen(seed=42, small=True)
    g = await _graph(topo)
    node = topo.sites[5]["nodes"][0]
    res = (await g.impact("node", node["nodeId"])).to_dict()
    assert res["impactedSites"] == [
        {
            "siteId": topo.sites[5]["siteId"],
            "kind": topo.sites[5]["kind"],
            "reason": "node",
            "cells": sorted(node["cells"]),
        }
    ]


@pytest.mark.parametrize("kind,ident", [("link", "LNK-999"), ("site", "SITE-999"), ("node", "X")])
async def test_unknown_targets(kind, ident):
    g = await _graph(from_netgen(seed=42, small=True))
    with pytest.raises(UnknownTarget):
        await g.impact(kind, ident)


def test_parents_form_a_homing_tree():
    topo = from_netgen(seed=42, small=True)
    kind = {s["siteId"]: s["kind"] for s in topo.sites}
    assert all(
        kind[c] == "access" and kind[p] == "hub" or kind[c] == "hub" and kind[p] == "core"
        for c, p in topo.parent.items()
    )
    assert {c for c in kind if kind[c] != "core"} == set(topo.parent)
    assert derive_parents(topo.sites, topo.links) == topo.parent


def test_load_json_round_trip(tmp_path):
    import json

    topo = from_netgen(seed=42, small=True)
    path = tmp_path / "topology.json"
    path.write_text(json.dumps({"sites": topo.sites, "links": topo.links}))
    again = load_json(str(path))
    assert again.sites == topo.sites and again.links == topo.links and again.parent == topo.parent
