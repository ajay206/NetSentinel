"""Step 15: turn an entity context into facets (words runbooks use) and citation node ids.

The facets are the graph's contribution to retrieval: e.g. LNK-012 is a fibre *access* link to a
single site, so last-mile runbooks fit; LNK-005 joins a core to a hub, so *ring / aggregation*
runbooks fit. The words are the ones the runbook titles and tags use.
"""

from __future__ import annotations

from typing import Any

SITE_FACETS = {
    "access": {"access", "single-site", "last-mile"},
    "hub": {"ring", "aggregation", "transport"},
    "core": {"core", "router"},
}
NODE_FACETS = {
    "router": {"router"},
    "gNB": {"gnb", "baseband", "radio"},
    "eNB": {"radio"},
}


# Type-level facets only say what *kind of element* it is (a link carries backhaul, a cell has
# sectors); they are weaker evidence than kind-level facets (access vs ring), see rerank.py.
TYPE_FACETS = {"link": {"link", "backhaul"}, "cell": {"cell", "sector"}}


def type_facets(ctx: dict[str, Any]) -> set[str]:
    return set(TYPE_FACETS.get(str(ctx.get("type")), set()))


def facets(ctx: dict[str, Any]) -> set[str]:
    """Kind-level facets: what the graph says about this element (access / ring / core ...)."""
    out: set[str] = set()
    if ctx.get("type") == "link" and ctx.get("link"):
        link = ctx["link"]
        if link["role"] == "access":
            out |= SITE_FACETS["access"]
        elif "hub" in (link.get("aKind"), link.get("bKind")):
            out |= SITE_FACETS["hub"]
        else:
            out |= {"core", "router", "transport"}
        if link.get("kind") == "microwave":
            out.add("microwave")
        return out
    site = ctx.get("site") or {}
    if ctx.get("type") == "cell" and ctx.get("node"):
        out |= NODE_FACETS.get(ctx["node"]["kind"], set()) & {"radio"}
    elif ctx.get("type") == "node" and ctx.get("node"):
        out |= NODE_FACETS.get(ctx["node"]["kind"], set())
    else:
        out |= SITE_FACETS.get(site.get("kind", ""), set())
    return out


def node_ids(ctx: dict[str, Any]) -> list[str]:
    """The graph nodes a citation can point at: the entity, its site, uplink and parent."""
    ids = [ctx["id"]]
    if ctx.get("link"):
        ids += [ctx["link"]["a"], ctx["link"]["b"]]
    site = (ctx.get("site") or {}).get("siteId")
    if site:
        ids.append(site)
        if ctx.get("parent"):
            up = next(
                (x["linkId"] for x in ctx.get("links", []) if x["peer"] == ctx["parent"]), None
            )
            ids += [i for i in (up, ctx["parent"]) if i]
    seen: list[str] = []
    for i in ids:
        if i not in seen:
            seen.append(i)
    return seen


def summary(ctx: dict[str, Any]) -> str:
    if ctx.get("link"):
        x = ctx["link"]
        ends = f"{x['a']} ({x['aKind']}) - {x['b']} ({x['bKind']})"
        return f"{x['linkId']} is a {x['kind']} {x['role']} link {ends}"
    site = ctx.get("site") or {}
    head = ctx["id"]
    if ctx.get("node"):
        head = f"{ctx['id']} ({ctx['node']['kind']}) at {site.get('siteId')}"
    text = f"{head}: {site.get('kind')} site {site.get('name')} in {site.get('region')}"
    if ctx.get("parent"):
        text += f", homed on {ctx['parent']}"
    if ctx.get("children"):
        text += f", serves {', '.join(ctx['children'])}"
    return text
