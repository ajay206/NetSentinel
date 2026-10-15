"""Graph backends for topology-service.

``Neo4jGraph`` answers impact / RCA questions with Cypher on the knowledge graph; ``MemoryGraph``
gives the same answers with a breadth-first search, for tests and for running without Neo4j
(``GRAPH_BACKEND=memory``). Both share the semantics in ``impact()``:

* a **link** failure isolates every non-core site that no longer reaches any core site;
* a **site** failure takes the site down and isolates whatever only reached core through it;
* a **node** failure only loses that node's cells (transport is modelled at site level).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from .model import TopoData
from .queries import CATALOGUE, NamedQuery

TargetType = Literal["link", "site", "node"]
MAX_HOPS = 8  # longest core path searched by the Cypher impact query (small: 2, full: 3)


class UnknownTarget(LookupError):
    pass


@dataclass
class ImpactResult:
    target_type: TargetType
    target_id: str
    impacted: list[dict[str, Any]] = field(default_factory=list)
    backend: str = "memory"
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": {"type": self.target_type, "id": self.target_id},
            "impactedSites": self.impacted,
            "cellsLost": sum(len(s["cells"]) for s in self.impacted),
            "sitesIsolated": sum(1 for s in self.impacted if s["reason"] == "isolated"),
            "backend": self.backend,
            "elapsedMs": round(self.elapsed_ms, 2),
        }


class Graph(Protocol):
    kind: str

    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def load(self, topo: TopoData, runbooks: list[dict[str, Any]] | None = None) -> dict: ...
    async def summary(self) -> dict[str, int]: ...
    async def impact(self, target_type: TargetType, target_id: str) -> ImpactResult: ...
    async def run_named(self, name: str, params: dict[str, Any]) -> list[dict[str, Any]]: ...
    async def add_alarm(self, alarm: dict[str, Any]) -> None: ...


def _order(impacted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank = {"failed": 0, "node": 1, "isolated": 2}
    for s in impacted:
        s["cells"] = sorted(s["cells"])
    return sorted(impacted, key=lambda s: (rank[s["reason"]], s["siteId"]))


# --------------------------------------------------------------------------- in-memory


class MemoryGraph:
    kind = "memory"

    def __init__(self) -> None:
        self.topo: TopoData | None = None
        self.alarms: dict[str, dict[str, Any]] = {}

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def load(self, topo: TopoData, runbooks: list[dict[str, Any]] | None = None) -> dict:
        self.topo = topo
        self.runbooks = list(runbooks or [])
        return {**topo.counts(), "runbooks": len(self.runbooks)}

    def _t(self) -> TopoData:
        if self.topo is None:
            raise RuntimeError("graph not loaded")
        return self.topo

    async def summary(self) -> dict[str, int]:
        t = self._t()
        return {
            **t.counts(),
            "alarms": len(self.alarms),
            "runbooks": len(getattr(self, "runbooks", [])),
        }

    async def add_alarm(self, alarm: dict[str, Any]) -> None:
        if alarm.get("id") and alarm.get("siteId"):
            self.alarms[str(alarm["id"])] = alarm

    async def run_named(self, name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError("named Cypher queries need GRAPH_BACKEND=neo4j")

    async def impact(self, target_type: TargetType, target_id: str) -> ImpactResult:
        start = time.perf_counter()
        t = self._t()
        sites = {s["siteId"]: s for s in t.sites}
        cells_of = {sid: [c for n in s["nodes"] for c in n["cells"]] for sid, s in sites.items()}
        impacted: list[dict[str, Any]] = []
        failed_links: set[str] = set()
        failed_sites: set[str] = set()
        if target_type == "link":
            if target_id not in t.link_ids:
                raise UnknownTarget(target_id)
            failed_links.add(target_id)
        elif target_type == "site":
            if target_id not in sites:
                raise UnknownTarget(target_id)
            failed_sites.add(target_id)
            impacted.append(
                {
                    "siteId": target_id,
                    "kind": sites[target_id]["kind"],
                    "reason": "failed",
                    "cells": cells_of[target_id],
                }
            )
        else:
            for s in t.sites:
                for n in s["nodes"]:
                    if n["nodeId"] == target_id:
                        impacted.append(
                            {
                                "siteId": s["siteId"],
                                "kind": s["kind"],
                                "reason": "node",
                                "cells": list(n["cells"]),
                            }
                        )
            if not impacted:
                raise UnknownTarget(target_id)
            return ImpactResult("node", target_id, _order(impacted), "memory", _ms(start))

        adj: dict[str, list[str]] = {sid: [] for sid in sites}
        for link in t.links:
            if link["linkId"] in failed_links:
                continue
            a, b = link["a"], link["b"]
            if a in failed_sites or b in failed_sites:
                continue
            adj[a].append(b)
            adj[b].append(a)
        reach = {sid for sid, s in sites.items() if s["kind"] == "core" and sid not in failed_sites}
        queue = deque(reach)
        while queue:
            for peer in adj[queue.popleft()]:
                if peer not in reach:
                    reach.add(peer)
                    queue.append(peer)
        for sid, s in sites.items():
            if sid not in reach and sid not in failed_sites:
                impacted.append(
                    {"siteId": sid, "kind": s["kind"], "reason": "isolated", "cells": cells_of[sid]}
                )
        return ImpactResult(target_type, target_id, _order(impacted), "memory", _ms(start))


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


# --------------------------------------------------------------------------- Neo4j

SCHEMA = (
    "CREATE CONSTRAINT site_id IF NOT EXISTS FOR (s:Site) REQUIRE s.siteId IS UNIQUE",
    "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Node) REQUIRE n.nodeId IS UNIQUE",
    "CREATE CONSTRAINT cell_id IF NOT EXISTS FOR (c:Cell) REQUIRE c.cellId IS UNIQUE",
    "CREATE CONSTRAINT alarm_id IF NOT EXISTS FOR (a:Alarm) REQUIRE a.alarmId IS UNIQUE",
    "CREATE CONSTRAINT runbook_id IF NOT EXISTS FOR (r:Runbook) REQUIRE r.runbookId IS UNIQUE",
    "CREATE CONSTRAINT ticket_id IF NOT EXISTS FOR (t:Ticket) REQUIRE t.ticketId IS UNIQUE",
    "CREATE INDEX link_id IF NOT EXISTS FOR ()-[l:LINK]-() ON (l.linkId)",
)

CLEAR_TOPOLOGY = """
MATCH (n) WHERE n:Site OR n:Node OR n:Cell OR n:Runbook
DETACH DELETE n
"""

LOAD_SITES = """
UNWIND $sites AS s
MERGE (site:Site {siteId: s.siteId})
SET site.name = s.name, site.region = s.region, site.kind = s.kind,
    site.lat = s.lat, site.lon = s.lon
WITH site, s
UNWIND s.nodes AS n
MERGE (node:Node {nodeId: n.nodeId})
SET node.kind = n.kind, node.siteId = s.siteId
MERGE (site)-[:HAS_NODE]->(node)
WITH node, n, s
UNWIND n.cells AS c
MERGE (cell:Cell {cellId: c})
SET cell.nodeId = n.nodeId, cell.siteId = s.siteId
MERGE (node)-[:HAS_CELL]->(cell)
"""

LOAD_LINKS = """
UNWIND $links AS l
MATCH (a:Site {siteId: l.a}), (b:Site {siteId: l.b})
MERGE (a)-[r:LINK {linkId: l.linkId}]->(b)
SET r.kind = l.kind, r.role = l.role
"""

LOAD_PARENTS = """
UNWIND $pairs AS p
MATCH (parent:Site {siteId: p.parent}), (child:Site {siteId: p.child})
MERGE (parent)-[:PARENT_OF]->(child)
"""

LOAD_RUNBOOKS = """
UNWIND $runbooks AS r
MERGE (rb:Runbook {runbookId: r.runbookId})
SET rb.title = r.title, rb.faultType = r.faultType
"""

ADD_ALARM = """
MATCH (s:Site {siteId: $siteId})
MERGE (a:Alarm {alarmId: $alarmId})
SET a.siteId = $siteId, a.severity = $severity, a.specificProblem = $specificProblem,
    a.raisedAt = $raisedAt
MERGE (a)-[:RAISED_ON]->(s)
"""

# The impact query: sites (other than the failed one) with no LINK path to a working core
# site that avoids the failed link / site. Bounded path length keeps it cheap on this graph.
IMPACT_ISOLATED = f"""
MATCH (s:Site)
WHERE s.siteId <> $failedSite
  AND NOT (s.kind = 'core')
  AND NOT EXISTS {{
    MATCH p = (s)-[:LINK*1..{MAX_HOPS}]-(c:Site {{kind: 'core'}})
    WHERE c.siteId <> $failedSite
      AND none(r IN relationships(p) WHERE r.linkId = $failedLink)
      AND none(n IN nodes(p) WHERE n.siteId = $failedSite)
  }}
OPTIONAL MATCH (s)-[:HAS_NODE]->(:Node)-[:HAS_CELL]->(cell:Cell)
RETURN s.siteId AS siteId, s.kind AS kind, collect(cell.cellId) AS cells
ORDER BY siteId
"""

SITE_CELLS = """
MATCH (s:Site {siteId: $siteId})
OPTIONAL MATCH (s)-[:HAS_NODE]->(:Node)-[:HAS_CELL]->(cell:Cell)
RETURN s.siteId AS siteId, s.kind AS kind, collect(cell.cellId) AS cells
"""

NODE_CELLS = """
MATCH (s:Site)-[:HAS_NODE]->(n:Node {nodeId: $nodeId})
OPTIONAL MATCH (n)-[:HAS_CELL]->(cell:Cell)
RETURN s.siteId AS siteId, s.kind AS kind, collect(cell.cellId) AS cells
"""

LINK_EXISTS = "MATCH ()-[r:LINK {linkId: $linkId}]-() RETURN count(r) > 0 AS ok"


class Neo4jGraph:
    kind = "neo4j"

    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import AsyncGraphDatabase

        self.driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_pool_size=10,
            connection_timeout=5,
            # "constraint already exists" / indexed cartesian-product notes are INFO noise
            notifications_min_severity="WARNING",
        )

    async def start(self) -> None:
        await self.driver.verify_connectivity()
        for stmt in SCHEMA:
            await self.driver.execute_query(stmt)

    async def close(self) -> None:
        await self.driver.close()

    async def _rows(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        records, _, _ = await self.driver.execute_query(cypher, params, routing_="r")
        return [r.data() for r in records]

    async def load(self, topo: TopoData, runbooks: list[dict[str, Any]] | None = None) -> dict:
        """Replace the topology in ONE write transaction, so readers never see a half graph.

        Alarms and tickets are kept (they re-attach to sites by siteId on the next alarm)."""
        pairs = [{"parent": p, "child": c} for c, p in topo.parent.items()]

        async def work(tx: Any) -> None:
            await tx.run(CLEAR_TOPOLOGY)
            await tx.run(LOAD_SITES, sites=topo.sites)
            await tx.run(LOAD_LINKS, links=topo.links)
            await tx.run(LOAD_PARENTS, pairs=pairs)
            if runbooks:
                await tx.run(LOAD_RUNBOOKS, runbooks=runbooks)

        async with self.driver.session() as session:
            await session.execute_write(work)
        return {**topo.counts(), "runbooks": len(runbooks or [])}

    async def summary(self) -> dict[str, int]:
        rows = await self.run_named("graph_summary", {})
        return {k: int(v) for k, v in (rows[0] if rows else {}).items()}

    async def add_alarm(self, alarm: dict[str, Any]) -> None:
        if not (alarm.get("id") and alarm.get("siteId")):
            return
        await self.driver.execute_query(
            ADD_ALARM,
            {
                "alarmId": str(alarm["id"]),
                "siteId": str(alarm["siteId"]),
                "severity": alarm.get("perceivedSeverity"),
                "specificProblem": alarm.get("specificProblem"),
                "raisedAt": alarm.get("alarmRaisedTime"),
            },
        )

    async def run_named(self, name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        q: NamedQuery = CATALOGUE[name]
        missing = [p for p in q.params if p not in params]
        if missing:
            raise ValueError(f"missing parameters: {', '.join(missing)}")
        return await self._rows(q.cypher, **{p: params[p] for p in q.params})

    async def impact(self, target_type: TargetType, target_id: str) -> ImpactResult:
        start = time.perf_counter()
        impacted: list[dict[str, Any]] = []
        failed_link, failed_site = "", ""
        if target_type == "node":
            rows = await self._rows(NODE_CELLS, nodeId=target_id)
            if not rows:
                raise UnknownTarget(target_id)
            impacted = [{**r, "reason": "node"} for r in rows]
            return ImpactResult("node", target_id, _order(impacted), "neo4j", _ms(start))
        if target_type == "link":
            ok = await self._rows(LINK_EXISTS, linkId=target_id)
            if not (ok and ok[0]["ok"]):
                raise UnknownTarget(target_id)
            failed_link = target_id
        else:
            rows = await self._rows(SITE_CELLS, siteId=target_id)
            if not rows:
                raise UnknownTarget(target_id)
            impacted.append({**rows[0], "reason": "failed"})
            failed_site = target_id
        rows = await self._rows(IMPACT_ISOLATED, failedLink=failed_link, failedSite=failed_site)
        impacted += [{**r, "reason": "isolated"} for r in rows]
        return ImpactResult(target_type, target_id, _order(impacted), "neo4j", _ms(start))


__all__ = ["CATALOGUE", "Graph", "ImpactResult", "MemoryGraph", "Neo4jGraph", "UnknownTarget"]
