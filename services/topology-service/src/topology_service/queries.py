"""Catalogue of named, parameterised, read-only Cypher queries for the telecom KG.

All queries use parameters exclusively ($param). No string formatting of user input.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NamedQuery:
    name: str
    description: str
    cypher: str
    params: tuple[str, ...]


CATALOGUE: dict[str, NamedQuery] = {
    "site_by_id": NamedQuery(
        name="site_by_id",
        description="Site properties as map plus node and cell counts.",
        cypher=(
            "MATCH (s:Site {siteId: $siteId}) "
            "OPTIONAL MATCH (s)-[:HAS_NODE]->(n:Node) "
            "OPTIONAL MATCH (n)-[:HAS_CELL]->(c:Cell) "
            "WITH s, count(DISTINCT n) AS nodeCount, count(DISTINCT c) AS cellCount "
            "RETURN s {.*, nodeCount: nodeCount, cellCount: cellCount} AS site"
        ),
        params=("siteId",),
    ),
    "nodes_of_site": NamedQuery(
        name="nodes_of_site",
        description="Nodes of a site with cell counts ordered by nodeId.",
        cypher=(
            "MATCH (s:Site {siteId: $siteId})-[:HAS_NODE]->(n:Node) "
            "OPTIONAL MATCH (n)-[:HAS_CELL]->(c:Cell) "
            "RETURN n.nodeId AS nodeId, n.kind AS kind, count(c) AS cellCount "
            "ORDER BY n.nodeId"
        ),
        params=("siteId",),
    ),
    "cells_of_site": NamedQuery(
        name="cells_of_site",
        description="Cell IDs of a site ordered.",
        cypher=(
            "MATCH (s:Site {siteId: $siteId})-[:HAS_NODE]->(:Node)-[:HAS_CELL]->(c:Cell) "
            "RETURN c.cellId AS cellId ORDER BY c.cellId"
        ),
        params=("siteId",),
    ),
    "site_of_cell": NamedQuery(
        name="site_of_cell",
        description="Site and node for a given cell.",
        cypher=(
            "MATCH (c:Cell {cellId: $cellId})<-[:HAS_CELL]-(n:Node)<-[:HAS_NODE]-(s:Site) "
            "RETURN s.siteId AS siteId, n.nodeId AS nodeId"
        ),
        params=("cellId",),
    ),
    "links_of_site": NamedQuery(
        name="links_of_site",
        description="Links of a site with peer siteId ordered by linkId.",
        cypher=(
            "MATCH (s:Site {siteId: $siteId})-[l:LINK]-(peer:Site) "
            "RETURN l.linkId AS linkId, l.kind AS kind, l.role AS role, "
            "peer.siteId AS peerSiteId ORDER BY l.linkId"
        ),
        params=("siteId",),
    ),
    "link_by_id": NamedQuery(
        name="link_by_id",
        description="Link details with both endpoint siteIds.",
        cypher=(
            "MATCH (a:Site)-[l:LINK {linkId: $linkId}]->(b:Site) "
            "RETURN l.linkId AS linkId, l.kind AS kind, l.role AS role, "
            "a.siteId AS a, b.siteId AS b"
        ),
        params=("linkId",),
    ),
    "neighbours": NamedQuery(
        name="neighbours",
        description="Distinct sites within hops LINK hops with min distance.",
        cypher=(
            "MATCH path = (s:Site {siteId: $siteId})-[:LINK*1..4]-(n:Site) "
            "WHERE n.siteId <> $siteId "
            "WITH n, min(length(path)) AS hops "
            "WHERE hops <= $hops "
            "RETURN n.siteId AS siteId, n.kind AS kind, hops "
            "ORDER BY hops, n.siteId"
        ),
        params=("siteId", "hops"),
    ),
    "path_to_core": NamedQuery(
        name="path_to_core",
        description="Shortest path over LINK to any core site with siteIds and linkIds.",
        cypher=(
            "MATCH (s:Site {siteId: $siteId}), (c:Site {kind: 'core'}) "
            "MATCH p = shortestPath((s)-[:LINK*]-(c)) "
            "RETURN [n IN nodes(p) | n.siteId] AS siteIds, "
            "[r IN relationships(p) | r.linkId] AS linkIds "
            "ORDER BY length(p) LIMIT 1"
        ),
        params=("siteId",),
    ),
    "parent_chain": NamedQuery(
        name="parent_chain",
        description="Homing chain upward via PARENT_OF from site to core.",
        cypher=(
            "MATCH path = (a:Site)-[:PARENT_OF*0..4]->(s:Site {siteId: $siteId}) "
            "WITH a, length(path) AS up ORDER BY up "
            "RETURN collect(a.siteId) AS ancestors"
        ),
        params=("siteId",),
    ),
    "children_of_site": NamedQuery(
        name="children_of_site",
        description="Direct PARENT_OF children siteIds ordered.",
        cypher=(
            "MATCH (s:Site {siteId: $siteId})-[:PARENT_OF]->(c:Site) "
            "RETURN c.siteId AS siteId ORDER BY c.siteId"
        ),
        params=("siteId",),
    ),
    "downstream_sites": NamedQuery(
        name="downstream_sites",
        description="All descendants via PARENT_OF with depth ordered.",
        cypher=(
            "MATCH path = (s:Site {siteId: $siteId})-[:PARENT_OF*1..4]->(d:Site) "
            "RETURN d.siteId AS siteId, length(path) AS depth "
            "ORDER BY depth, d.siteId"
        ),
        params=("siteId",),
    ),
    "single_homed_sites": NamedQuery(
        name="single_homed_sites",
        description="Access/hub sites with exactly one distinct LINK peer.",
        cypher=(
            "MATCH (s:Site) WHERE s.kind IN ['access', 'hub'] "
            "WITH s, COUNT { (s)-[:LINK]-(:Site) } AS peers "
            "WHERE peers = 1 "
            "MATCH (s)-[l:LINK]-(:Site) "
            "RETURN s.siteId AS siteId, s.kind AS kind, l.linkId AS linkId "
            "ORDER BY s.siteId"
        ),
        params=(),
    ),
    "links_by_role": NamedQuery(
        name="links_by_role",
        description="Links filtered by role with endpoints and kind ordered.",
        cypher=(
            "MATCH (a:Site)-[l:LINK {role: $role}]->(b:Site) "
            "RETURN l.linkId AS linkId, a.siteId AS a, b.siteId AS b, l.kind AS kind "
            "ORDER BY l.linkId"
        ),
        params=("role",),
    ),
    "site_counts_by_region": NamedQuery(
        name="site_counts_by_region",
        description="Site counts grouped by region and kind ordered.",
        cypher=(
            "MATCH (s:Site) "
            "RETURN s.region AS region, s.kind AS kind, count(*) AS count "
            "ORDER BY region, kind"
        ),
        params=(),
    ),
    "degree_ranking": NamedQuery(
        name="degree_ranking",
        description="Sites ranked by LINK degree descending with limit.",
        cypher=(
            "MATCH (s:Site) "
            "WITH s, COUNT { (s)-[:LINK]-() } AS degree "
            "RETURN s.siteId AS siteId, s.kind AS kind, degree "
            "ORDER BY degree DESC, s.siteId LIMIT $limit"
        ),
        params=("limit",),
    ),
    "active_alarms_at_site": NamedQuery(
        name="active_alarms_at_site",
        description="Active alarms at a site newest first limited to 50.",
        cypher=(
            "MATCH (a:Alarm)-[:RAISED_ON]->(s:Site {siteId: $siteId}) "
            "RETURN a.alarmId AS alarmId, a.severity AS severity, "
            "a.specificProblem AS specificProblem, a.raisedAt AS raisedAt "
            "ORDER BY a.raisedAt DESC LIMIT 50"
        ),
        params=("siteId",),
    ),
    "sites_with_alarms": NamedQuery(
        name="sites_with_alarms",
        description="Sites with alarm counts and worst severity rank limited to 50.",
        cypher=(
            "MATCH (a:Alarm)-[:RAISED_ON]->(s:Site) "
            "WITH s, count(a) AS alarmCount, "
            "max(CASE a.severity "
            "WHEN 'critical' THEN 4 WHEN 'major' THEN 3 "
            "WHEN 'minor' THEN 2 WHEN 'warning' THEN 1 ELSE 0 END) AS worst "
            "RETURN s.siteId AS siteId, alarmCount, worst "
            "ORDER BY worst DESC, alarmCount DESC LIMIT 50"
        ),
        params=(),
    ),
    "alarm_neighbourhood": NamedQuery(
        name="alarm_neighbourhood",
        description="Sites within 2 LINK hops of site that have alarms with counts.",
        cypher=(
            "MATCH (s:Site {siteId: $siteId})-[:LINK*1..2]-(n:Site) "
            "WHERE n <> s "
            "WITH DISTINCT n "
            "MATCH (a:Alarm)-[:RAISED_ON]->(n) "
            "RETURN n.siteId AS siteId, count(a) AS alarmCount "
            "ORDER BY alarmCount DESC, n.siteId"
        ),
        params=("siteId",),
    ),
    "runbooks_for_fault": NamedQuery(
        name="runbooks_for_fault",
        description="Runbooks matching a faultType ordered by title.",
        cypher=(
            "MATCH (r:Runbook {faultType: $faultType}) "
            "RETURN r.runbookId AS runbookId, r.title AS title "
            "ORDER BY r.title"
        ),
        params=("faultType",),
    ),
    "graph_summary": NamedQuery(
        name="graph_summary",
        description="Global counts of all major entities in a single row.",
        cypher=(
            "CALL { MATCH (s:Site) RETURN count(s) AS sites } "
            "CALL { MATCH (n:Node) RETURN count(n) AS nodes } "
            "CALL { MATCH (c:Cell) RETURN count(c) AS cells } "
            "CALL { MATCH ()-[l:LINK]->() RETURN count(l) AS links } "
            "CALL { MATCH (a:Alarm) RETURN count(a) AS alarms } "
            "CALL { MATCH (r:Runbook) RETURN count(r) AS runbooks } "
            "RETURN sites, nodes, cells, links, alarms, runbooks"
        ),
        params=(),
    ),
}


def get(name: str) -> NamedQuery:
    """Return NamedQuery by name or raise KeyError."""
    try:
        return CATALOGUE[name]
    except KeyError as exc:
        raise KeyError(f"unknown query {name}") from exc


def describe() -> list[dict[str, object]]:
    """Return list of dicts with name, description, params for each query."""
    return [
        {"name": q.name, "description": q.description, "params": list(q.params)}
        for q in CATALOGUE.values()
    ]
