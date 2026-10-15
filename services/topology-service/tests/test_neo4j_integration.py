"""W14: Neo4j and the in-memory graph give identical impact answers (needs a real Neo4j).

Runs only when NEO4J_TEST_URI is set, e.g. against the compose `graph` profile:
    NEO4J_TEST_URI=bolt://localhost:7687 NEO4J_TEST_PASSWORD=... uv run pytest -k neo4j
"""

from __future__ import annotations

import os
import statistics
import time

import pytest
from topology_service import queries
from topology_service.graph import MemoryGraph, Neo4jGraph
from topology_service.load import read_runbooks
from topology_service.model import from_netgen

URI = os.getenv("NEO4J_TEST_URI")
pytestmark = pytest.mark.skipif(not URI, reason="NEO4J_TEST_URI not set")


@pytest.mark.parametrize("small", [True, False], ids=["small", "full"])
async def test_neo4j_matches_memory_and_is_fast(small):
    topo = from_netgen(seed=42, small=small)
    neo = Neo4jGraph(URI or "", "neo4j", os.getenv("NEO4J_TEST_PASSWORD", ""))
    await neo.start()
    try:
        await neo.load(topo, read_runbooks("data/runbooks"))
        await neo.load(topo)  # replaces in one transaction (small -> full -> small across runs)
        mem = MemoryGraph()
        await mem.load(topo)
        s = await neo.summary()
        assert (s["sites"], s["links"], s["cells"]) == (
            len(topo.sites),
            len(topo.links),
            topo.counts()["cells"],
        )
        timings = []
        targets = (
            [("link", x["linkId"]) for x in topo.links]
            + [("site", x["siteId"]) for x in topo.sites]
            + [("node", topo.sites[3]["nodes"][0]["nodeId"])]
        )
        for kind, ident in targets:
            t0 = time.perf_counter()
            a = (await neo.impact(kind, ident)).to_dict()
            timings.append((time.perf_counter() - t0) * 1000)
            b = (await mem.impact(kind, ident)).to_dict()
            assert a["impactedSites"] == b["impactedSites"], (kind, ident)
        p50 = statistics.median(timings)
        print(f"neo4j impact p50={p50:.1f} ms max={max(timings):.1f} ms n={len(timings)}")
        assert p50 < 100
        # every catalogue query runs (smoke params)
        params = {
            "siteId": "SITE-004",
            "cellId": topo.sites[3]["nodes"][0]["cells"][0],
            "linkId": "LNK-012",
            "hops": 2,
            "role": "access",
            "limit": 5,
            "faultType": "fibre_cut",
        }
        for name, q in queries.CATALOGUE.items():
            await neo.run_named(name, {p: params[p] for p in q.params})
        chain = await neo.run_named("parent_chain", {"siteId": "SITE-010"})
        assert chain[0]["ancestors"][0] == "SITE-010" and chain[0]["ancestors"][-1] in {
            "SITE-001",
            "SITE-002",
        }
    finally:
        await neo.close()
