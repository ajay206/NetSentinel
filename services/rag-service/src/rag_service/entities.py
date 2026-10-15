"""Step 15: entity linking for Graph RAG.

Finds network elements in free text and normalises them to graph ids:

* exact ids: ``SITE-010``, ``LNK-012``, ``SITE-010-N1`` (node), ``SITE-010-N1-C2`` (cell);
* loose aliases: ``site 10``, ``SITE10``, ``link 12``, ``L-12``, ``LNK12``;
* site names from the topology: ``Central-Access-5``, ``central access 5``;
* one relation hop: ``the hub of SITE-010`` / ``upstream of site 10`` -> the parent site.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .topology import Topology

_CELL = re.compile(r"\bSITE-?(\d{1,3})-N(\d{1,2})-C(\d{1,2})\b", re.I)
_NODE = re.compile(r"\bSITE-?(\d{1,3})-N(\d{1,2})\b(?!-C)", re.I)
_SITE = re.compile(r"\b(?:SITE-?|site\s+)(\d{1,3})\b(?!-N)", re.I)
_LINK = re.compile(r"\b(?:LNK-?|L-|link\s+)(\d{1,3})\b", re.I)
_REL = re.compile(
    r"\b(?:the\s+)?(?:hub|parent|upstream(?:\s+site)?|aggregation\s+site)\s+"
    r"(?:of|for|serving|above|behind)\s+$",
    re.I,
)


@dataclass(frozen=True)
class Entity:
    id: str
    type: str  # site | link | node | cell
    mention: str
    via: str  # id | alias | name | relation

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class EntityLinker:
    def __init__(self, topology: Topology | None) -> None:
        self.topology = topology
        names = topology.names() if topology else {}
        # longest names first so "North-Access-10" wins over "North-Access-1"
        self._names = sorted(
            ((_norm(n), sid) for n, sid in names.items()), key=lambda x: -len(x[0])
        )

    def link(self, text: str, limit: int = 3) -> list[Entity]:
        found: list[tuple[int, Entity]] = []
        taken: list[tuple[int, int]] = []

        def free(a: int, b: int) -> bool:
            return all(b <= x or a >= y for x, y in taken)

        def add(pos: int, end: int, e: Entity) -> None:
            if free(pos, end):
                taken.append((pos, end))
                found.append((pos, e))

        for rx, etype, fmt in (
            (_CELL, "cell", lambda m: f"SITE-{int(m[1]):03d}-N{int(m[2])}-C{int(m[3])}"),
            (_NODE, "node", lambda m: f"SITE-{int(m[1]):03d}-N{int(m[2])}"),
            (_SITE, "site", lambda m: f"SITE-{int(m[1]):03d}"),
            (_LINK, "link", lambda m: f"LNK-{int(m[1]):03d}"),
        ):
            for m in rx.finditer(text):
                eid = fmt(m)
                via = "id" if m[0].upper() == eid else "alias"
                add(m.start(), m.end(), Entity(eid, etype, m[0], via))
        low = _norm(text)
        for name, sid in self._names:
            idx = f" {low} ".find(f" {name} ")
            if idx >= 0:
                # map the normalised position back approximately; only used for ordering
                pos = 10_000 + idx
                add(pos, pos + len(name), Entity(sid, "site", name, "name"))
        found.sort(key=lambda x: x[0])
        out: list[Entity] = []
        for pos, e in found:
            if pos < 10_000 and e.type == "site" and self.topology is not None:
                if _REL.search(text[:pos]):
                    ctx = self.topology.context(e.id)
                    if ctx and ctx.get("parent"):
                        e = Entity(ctx["parent"], "site", f"parent of {e.id}", "relation")
            if all(o.id != e.id for o in out):
                out.append(e)
        return out[:limit]
