"""Load the network (and runbook metadata) into the knowledge graph.

Usage (inside compose, no host tooling):
    docker compose --profile graph run --rm topology-service \
        python -m topology_service.load --topology data/topology.json
Without --topology the netgen topology for TOPOLOGY_SEED / TOPOLOGY_FULL is used. MERGE-based,
so re-running is idempotent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from .model import TopoData, from_netgen, load_json

_FRONT = re.compile(r"^---\n(.*?)\n---", re.S)


def read_runbooks(directory: str | Path) -> list[dict[str, Any]]:
    """id / title / faultType from the YAML-ish front matter of data/runbooks/*.md."""
    out: list[dict[str, Any]] = []
    for path in sorted(Path(directory).glob("RB-*.md")):
        m = _FRONT.match(path.read_text(encoding="utf-8"))
        if not m:
            continue
        meta = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        if meta.get("id"):
            out.append(
                {
                    "runbookId": meta["id"],
                    "title": meta.get("title", meta["id"]),
                    "faultType": meta.get("faultType", ""),
                }
            )
    return out


def resolve_topology(path: str | None, seed: int, full: bool) -> TopoData:
    return load_json(path) if path else from_netgen(seed=seed, small=not full)


async def _main(args: argparse.Namespace) -> dict[str, Any]:
    from . import main as svc

    topo = resolve_topology(args.topology, args.seed, args.full)
    runbooks = read_runbooks(args.runbooks) if Path(args.runbooks).is_dir() else []
    graph = svc.make_graph()
    await graph.start()
    try:
        return await graph.load(topo, runbooks)
    finally:
        await graph.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load topology + runbooks into the graph")
    p.add_argument(
        "--topology",
        default=os.getenv("TOPOLOGY_FILE") or None,
        help="netgen topology JSON (default: $TOPOLOGY_FILE, else build from --seed)",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--full", action="store_true", help="60-site topology instead of 12")
    p.add_argument("--runbooks", default=os.getenv("RUNBOOKS_DIR", "data/runbooks"))
    counts = asyncio.run(_main(p.parse_args(argv)))
    print(json.dumps({"loaded": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
