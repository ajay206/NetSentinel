"""Step 15: write the graph part of data/eval/qa.jsonl (deterministic, synthetic topology).

These questions name a network element (id, alias like ``L-12``, or site name) but leave out the
words that decide the runbook; the right answer depends on a graph fact: is the link an access
link or a core/hub link, is the site an access site or a hub, is the element a link or a cell,
which hub serves a site. Each line records the expected runbook, the entity ids and the catalogue
query the text-to-Cypher planner should pick.

Usage: uv run python scripts/gen_qa_graph.py            (rewrites the graph lines in qa.jsonl)
       uv run python scripts/gen_qa_graph.py --check    (exit 1 if qa.jsonl is stale)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from netgen import build_topology

QA = Path(__file__).resolve().parents[1] / "data/eval/qa.jsonl"

LINK_LOS = [
    "LOS alarm raised on {m}, what do I do",
    "{m} lost signal, optical power dropped to zero",
    "loss of light reported on {m}",
]
SITE_DARK = [
    "{m} lost all transmission, LOS on its uplink",
    "no light into {m}, everything there unreachable",
    "{m} unreachable after an optical alarm",
]
HUB_OF = [
    "the hub of {m} reports LOS on its transmission",
    "upstream site of {m} lost light",
]
LINK_UTIL = ["utilisation pinned at 95% on {m}", "{m} running hot, utilisation over 90%"]
CELL_UTIL = ["utilisation pinned at 95% on {m}", "{m} running hot, utilisation over 90%"]
CELL_DOWN = ["{m} went off air after a radio alarm", "{m} not carrying traffic, radio alarm active"]


def alias(link_id: str, i: int) -> str:
    n = int(link_id[4:])
    return [link_id, f"L-{n}", f"link {n}"][i % 3]


def build() -> list[dict]:
    topo = build_topology(seed=42, small=True).to_dict()
    sites = {s["siteId"]: s for s in topo["sites"]}
    links = topo["links"]
    out: list[dict] = []

    def add(q: str, expected: str, fault: str, entities: list[str], plan: str) -> None:
        out.append(
            {
                "query": q,
                "expected": expected,
                "faultType": fault,
                "category": "graph",
                "entities": entities,
                "plan": plan,
            }
        )

    # A. fibre LOS on a link: access link -> last-mile runbook, core-hub link -> ring runbook
    i = 0
    for x in links:
        kinds = {sites[x["a"]]["kind"], sites[x["b"]]["kind"]}
        if x["kind"] != "fibre" or kinds == {"core"}:
            continue
        rb = "RB-FIB-002" if x["role"] == "access" else "RB-FIB-001"
        for _ in range(2 if i < 6 else 1):
            add(
                LINK_LOS[i % 3].format(m=alias(x["linkId"], i)),
                rb,
                "fibre_cut",
                [x["linkId"]],
                "link_by_id",
            )
            i += 1
    # B. a dark site: access site (fibre uplink) -> last-mile, hub -> ring
    uplink_kind = {}
    for x in links:
        for s in (x["a"], x["b"]):
            if sites[s]["kind"] == "access":
                uplink_kind[s] = x["kind"]
    j = 0
    for sid, s in sites.items():
        if s["kind"] == "core" or uplink_kind.get(sid, "fibre") != "fibre":
            continue
        rb = "RB-FIB-002" if s["kind"] == "access" else "RB-FIB-001"
        for mention in [sid, s["name"]] if j % 2 == 0 else [s["name"]]:
            add(SITE_DARK[j % 3].format(m=mention), rb, "fibre_cut", [sid], "site_by_id")
        j += 1
    # C. one relation hop: the hub that serves an access site -> ring runbook
    for k, (sid, _s) in enumerate(x for x in sites.items() if x[1]["kind"] == "access"):
        add(HUB_OF[k % 2].format(m=sid), "RB-FIB-001", "fibre_cut", [sid], "parent_chain")
    # D. utilisation: a link -> backhaul saturation, a cell -> PRB congestion
    access_links = [x for x in links if x["role"] == "access"][:5]
    for k, x in enumerate(access_links):
        add(
            LINK_UTIL[k % 2].format(m=alias(x["linkId"], k)),
            "RB-CON-002",
            "congestion",
            [x["linkId"]],
            "link_by_id",
        )
    cells = [s["nodes"][0]["cells"][0] for s in sites.values() if s["kind"] != "core"][:5]
    for k, c in enumerate(cells):
        add(CELL_UTIL[k % 2].format(m=c), "RB-CON-001", "congestion", [c], "site_of_cell")
    # E. controls: radio fault on a cell (text alone should already work)
    for k, c in enumerate(cells[:4]):
        add(CELL_DOWN[k % 2].format(m=c), "RB-CEL-001", "cell_outage", [c], "site_of_cell")
    return out


def main(argv: list[str]) -> int:
    lines = [json.loads(x) for x in QA.read_text().splitlines() if x.strip()]
    text = [q for q in lines if q.get("category") != "graph"]
    want = text + build()
    rendered = "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in want)
    if "--check" in argv:
        ok = QA.read_text() == rendered
        print("qa.jsonl up to date" if ok else "qa.jsonl is stale: run scripts/gen_qa_graph.py")
        return 0 if ok else 1
    QA.write_text(rendered)
    print(f"wrote {QA}: {len(text)} text/paraphrase + {len(want) - len(text)} graph questions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
