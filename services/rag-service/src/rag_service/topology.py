"""Step 15: topology access for Graph RAG (entity context = one-hop neighbourhood).

``HttpTopology`` asks topology-service (``GET /graph/context/{id}``, Neo4j or memory backend);
``LocalTopology`` builds the same synthetic netgen topology in-process (seed 42 by default), so
rag-service, the benchmark and the tests work without the ``graph`` compose profile. Both return
the topology-service context shape (see services/topology-service ``graph.context``).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Protocol

import httpx

logger = logging.getLogger("rag-service.topology")

ENTITY_RE = re.compile(r"^(SITE-\d{3}(-N\d{1,2}(-C\d{1,2})?)?|LNK-\d{3})$")


def entity_type(eid: str) -> str | None:
    if re.fullmatch(r"SITE-\d{3}-N\d{1,2}-C\d{1,2}", eid):
        return "cell"
    if re.fullmatch(r"SITE-\d{3}-N\d{1,2}", eid):
        return "node"
    if re.fullmatch(r"SITE-\d{3}", eid):
        return "site"
    if re.fullmatch(r"LNK-\d{3}", eid):
        return "link"
    return None


class Topology(Protocol):
    source: str

    def context(self, entity_id: str) -> dict[str, Any] | None: ...
    def names(self) -> dict[str, str]: ...


class LocalTopology:
    """In-process netgen topology (deterministic; same seed as the rest of the stack)."""

    source = "local"

    def __init__(self, seed: int | None = None, small: bool | None = None) -> None:
        from netgen import build_topology

        seed = int(os.getenv("TOPOLOGY_SEED", "42")) if seed is None else seed
        small = (os.getenv("TOPOLOGY_FULL", "0") != "1") if small is None else small
        data = build_topology(seed=seed, small=small).to_dict()
        self.sites = {s["siteId"]: s for s in data["sites"]}
        self.links = {x["linkId"]: x for x in data["links"]}
        self.parent = _derive_parents(data["sites"], data["links"])

    def names(self) -> dict[str, str]:
        return {s["name"]: sid for sid, s in self.sites.items()}

    def context(self, entity_id: str) -> dict[str, Any] | None:
        etype = entity_type(entity_id)
        ctx: dict[str, Any] = {"id": entity_id, "type": etype, "site": None, "node": None}
        ctx.update(link=None, parent=None, children=[], links=[], alarms=[])
        if etype == "link":
            x = self.links.get(entity_id)
            if x is None:
                return None
            ctx["link"] = {
                **{k: x[k] for k in ("linkId", "a", "b", "kind", "role")},
                "aKind": self.sites[x["a"]]["kind"],
                "bKind": self.sites[x["b"]]["kind"],
            }
            return ctx
        site_id = entity_id[:8] if etype else None
        site = self.sites.get(site_id or "")
        if site is None:
            return None
        if etype in ("node", "cell"):
            node_id = entity_id if etype == "node" else entity_id.rsplit("-", 1)[0]
            node = next((n for n in site["nodes"] if n["nodeId"] == node_id), None)
            if node is None or (etype == "cell" and entity_id not in node["cells"]):
                return None
            ctx["node"] = {"nodeId": node["nodeId"], "kind": node["kind"]}
        ctx["site"] = {k: site[k] for k in ("siteId", "name", "kind", "region")}
        ctx["parent"] = self.parent.get(site["siteId"])
        ctx["children"] = sorted(c for c, p in self.parent.items() if p == site["siteId"])
        ctx["links"] = sorted(
            (
                {
                    "linkId": x["linkId"],
                    "peer": x["b"] if x["a"] == site["siteId"] else x["a"],
                    "kind": x["kind"],
                    "role": x["role"],
                }
                for x in self.links.values()
                if site["siteId"] in (x["a"], x["b"])
            ),
            key=lambda x: x["linkId"],
        )
        return ctx


def _derive_parents(sites: list[dict], links: list[dict]) -> dict[str, str]:
    """Homing tree, as in topology-service: access -> its hub, hub -> first core it links to."""
    kind = {s["siteId"]: s["kind"] for s in sites}
    parent: dict[str, str] = {}
    for x in links:
        for child, up in ((x["a"], x["b"]), (x["b"], x["a"])):
            want = {"access": "hub", "hub": "core"}.get(kind[child])
            if want and kind[up] == want and child not in parent:
                parent[child] = up
    return parent


class HttpTopology:
    """topology-service over HTTP, falling back to the local topology when it is down."""

    def __init__(self, url: str, local: LocalTopology | None = None, timeout: float = 1.5) -> None:
        self.url = url.rstrip("/")
        self.local = local or LocalTopology()
        self.timeout = timeout
        self.transport: httpx.BaseTransport | None = None  # tests
        self.source = "topology-service"

    def names(self) -> dict[str, str]:
        return self.local.names()

    def context(self, entity_id: str) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as c:
                r = c.get(f"{self.url}/graph/context/{entity_id}")
            if r.status_code == 404:
                self.source = "topology-service"
                return None
            r.raise_for_status()
            self.source = "topology-service"
            data = r.json()
            data.pop("backend", None)
            return data
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "topology-service unavailable (%s); using local topology", type(exc).__name__
            )
            self.source = "local (topology-service unavailable)"
            return self.local.context(entity_id)


def get_topology() -> Topology | None:
    """GRAPH_CONTEXT=local (default) | http (TOPOLOGY_SERVICE_URL) | off."""
    mode = os.getenv("GRAPH_CONTEXT", "local")
    if mode == "off":
        return None
    if mode == "http":
        return HttpTopology(os.getenv("TOPOLOGY_SERVICE_URL", "http://localhost:8008"))
    return LocalTopology()
