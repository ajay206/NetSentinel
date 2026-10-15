"""Step 15: text-to-Cypher with schema prompting, restricted to the named query catalogue.

The planner never emits Cypher text. It maps a question (plus linked entities) to one of the
read-only catalogue queries of topology-service and its parameters; topology-service then runs
the fixed, parameterised Cypher. That removes the classic text-to-Cypher risks (writes, injected
clauses, unbounded traversals). An optional LLM planner gets a *schema prompt* (graph model +
catalogue) and must answer JSON; anything that fails validation falls back to the rule planner.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass

from .entities import Entity

SCHEMA = """\
Graph (Neo4j): (:Site {siteId, name, kind: core|hub|access, region})-[:HAS_NODE]->(:Node {nodeId,
kind})-[:HAS_CELL]->(:Cell {cellId}); (:Site)-[:LINK {linkId, kind: fibre|microwave, role:
core|access}]->(:Site); (:Site)-[:PARENT_OF]->(:Site) homing tree; (:Alarm)-[:RAISED_ON]->(:Site);
(:Runbook {runbookId, title, faultType})."""

# name -> (description, params). Must exist in topology-service's catalogue (checked in tests).
ALLOWED: dict[str, tuple[str, tuple[str, ...]]] = {
    "site_by_id": ("one site with node and cell counts", ("siteId",)),
    "link_by_id": ("one link with its endpoints", ("linkId",)),
    "site_of_cell": ("the site and node a cell belongs to", ("cellId",)),
    "nodes_of_site": ("nodes at a site", ("siteId",)),
    "links_of_site": ("links touching a site", ("siteId",)),
    "neighbours": ("sites within N link hops", ("siteId", "hops")),
    "parent_chain": ("homing chain from a site up to core", ("siteId",)),
    "downstream_sites": ("sites homed (directly or not) on a site", ("siteId",)),
    "path_to_core": ("shortest link path from a site to a core site", ("siteId",)),
    "active_alarms_at_site": ("alarms raised on a site", ("siteId",)),
}
PARAM_RE = {
    "siteId": re.compile(r"^SITE-\d{3}$"),
    "linkId": re.compile(r"^LNK-\d{3}$"),
    "cellId": re.compile(r"^SITE-\d{3}-N\d{1,2}-C\d{1,2}$"),
}
RULES = [
    (re.compile(r"\b(downstream|behind|served by|depend|children)\b", re.I), "downstream_sites"),
    (re.compile(r"\b(path|route)\b.*\bcore\b|\bto (the )?core\b", re.I), "path_to_core"),
    (re.compile(r"\b(neighbou?rs?|adjacent|nearby)\b", re.I), "neighbours"),
    (re.compile(r"\b(homed|upstream|parent|which hub)\b", re.I), "parent_chain"),
    (re.compile(r"\balarms?\b.*\b(on|at|raised)\b", re.I), "active_alarms_at_site"),
    (re.compile(r"\b(links?|uplinks?)\b.*\b(of|at|touching)\b", re.I), "links_of_site"),
    (re.compile(r"\bnodes?\b", re.I), "nodes_of_site"),
]


class PlanError(ValueError):
    pass


@dataclass(frozen=True)
class Plan:
    query: str
    params: dict
    planner: str  # rules | llm

    def to_dict(self) -> dict:
        return asdict(self)


def validate(name: str, params: dict) -> dict:
    if name not in ALLOWED:
        raise PlanError(f"query {name!r} is not in the catalogue")
    want = set(ALLOWED[name][1])
    if set(params) != want:
        raise PlanError(f"{name} needs params {sorted(want)}")
    clean: dict = {}
    for k, v in params.items():
        if k == "hops":
            if not isinstance(v, int) or not 1 <= v <= 4:
                raise PlanError("hops must be an integer 1-4")
        elif not (isinstance(v, str) and PARAM_RE[k].match(v)):
            raise PlanError(f"bad {k}")
        clean[k] = v
    return clean


def schema_prompt(question: str, entities: list[Entity]) -> str:
    cat = "\n".join(f"- {n}({', '.join(p)}): {d}" for n, (d, p) in ALLOWED.items())
    ents = ", ".join(f"{e.id} ({e.type})" for e in entities) or "none"
    return (
        f"{SCHEMA}\n\nYou may only choose one of these read-only queries:\n{cat}\n\n"
        f"Linked entities: {ents}\nQuestion: {question}\n"
        'Answer with JSON only: {"query": "<name>", "params": {...}}. Never write Cypher.'
    )


class RulePlanner:
    name = "rules"

    def plan(self, question: str, entities: list[Entity]) -> Plan | None:
        if not entities:
            return None
        e = entities[0]
        if e.type == "link":
            return Plan("link_by_id", {"linkId": e.id}, self.name)
        if e.type == "cell":
            return Plan("site_of_cell", {"cellId": e.id}, self.name)
        site = e.id[:8]
        if e.via == "relation":  # "the hub of SITE-010": walk up from the mentioned site
            return Plan("parent_chain", {"siteId": e.mention.split()[-1]}, self.name)
        for rx, name in RULES:
            if rx.search(question):
                params = {"siteId": site, "hops": 2} if name == "neighbours" else {"siteId": site}
                return Plan(name, params, self.name)
        if e.type == "node":
            return Plan("nodes_of_site", {"siteId": site}, self.name)
        return Plan("site_by_id", {"siteId": site}, self.name)


class LlmPlanner:
    """Schema-prompted planner; ``generate`` is any prompt -> text callable (e.g. Ollama)."""

    name = "llm"

    def __init__(self, generate: Callable[[str], str], fallback: RulePlanner | None = None):
        self.generate = generate
        self.fallback = fallback or RulePlanner()
        self.last_error: str | None = None

    def plan(self, question: str, entities: list[Entity]) -> Plan | None:
        self.last_error = None
        try:
            raw = self.generate(schema_prompt(question, entities))
            match = re.search(r"\{.*\}", raw, re.S)
            data = json.loads(match.group(0) if match else raw)
            params = validate(str(data["query"]), dict(data.get("params") or {}))
            return Plan(str(data["query"]), params, self.name)
        except Exception as exc:  # noqa: BLE001 - any bad output -> deterministic rules
            self.last_error = f"{type(exc).__name__}: {exc}"[:200]
            return self.fallback.plan(question, entities)
