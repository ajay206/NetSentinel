"""topology-service (W14): Neo4j knowledge graph + impact / RCA REST API.

On start it connects to Neo4j (``GRAPH_BACKEND=neo4j``, the compose default), creates the
constraints and loads the netgen topology plus runbook metadata (replacing any stale graph), so a
plain ``docker compose --profile graph up`` is enough. ``GRAPH_BACKEND=memory`` runs the same
API on an in-memory graph (tests, laptops without RAM for Neo4j). Optionally it consumes
``alarms.enriched`` and links Alarm nodes to their sites. Read-only API; the gateway enforces
RBAC (viewer to read, admin to reload). See ADR-014.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Response

from . import queries
from .graph import Graph, MemoryGraph, Neo4jGraph, TargetType, UnknownTarget, entity_type
from .load import read_runbooks, resolve_topology

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("topology-service")

GRAPH_BACKEND = os.getenv("GRAPH_BACKEND", "memory")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
TOPOLOGY_SEED = int(os.getenv("TOPOLOGY_SEED", "42"))
TOPOLOGY_FULL = os.getenv("TOPOLOGY_FULL", "0") == "1"
TOPOLOGY_FILE = os.getenv("TOPOLOGY_FILE") or None
RUNBOOKS_DIR = os.getenv("RUNBOOKS_DIR", "data/runbooks")
DISABLE_KAFKA = os.getenv("DISABLE_KAFKA", "1") == "1"
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
ENRICHED_TOPIC = os.getenv("ENRICHED_TOPIC", "alarms.enriched")

ID_RE = {
    "link": re.compile(r"^LNK-\d{3,4}$"),
    "site": re.compile(r"^SITE-\d{3,4}$"),
    "node": re.compile(r"^SITE-\d{3,4}-N\d{1,2}$"),
}

state: dict[str, Any] = {"ready": False, "error": None, "loaded": None, "alarms": 0}
graph: Graph = MemoryGraph()


def make_graph() -> Graph:
    if GRAPH_BACKEND == "neo4j":
        return Neo4jGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    return MemoryGraph()


async def init_graph(retries: int = 60, delay: float = 2.0) -> None:
    """Connect (Neo4j may still be starting), then load the configured topology."""
    global graph
    graph = make_graph()
    for attempt in range(1, retries + 1):
        try:
            await graph.start()
            break
        except Exception as exc:  # noqa: BLE001 - keep retrying; report the type only
            state["error"] = type(exc).__name__
            logger.warning("graph not ready (attempt %d): %s", attempt, type(exc).__name__)
            await asyncio.sleep(delay)
    else:
        return
    try:
        # Always (re)load: one write transaction of ~1k MERGEs, so the graph always matches the
        # configured topology (a stale small/full graph from an earlier run is replaced).
        topo = resolve_topology(TOPOLOGY_FILE, TOPOLOGY_SEED, TOPOLOGY_FULL)
        runbooks = read_runbooks(RUNBOOKS_DIR) if os.path.isdir(RUNBOOKS_DIR) else []
        state["loaded"] = await graph.load(topo, runbooks)
        logger.info("graph loaded: %s", state["loaded"])
        state.update(ready=True, error=None)
    except Exception as exc:  # noqa: BLE001
        state["error"] = type(exc).__name__
        logger.exception("graph load failed")


async def consume_alarms() -> None:
    from aiokafka import AIOKafkaConsumer

    while True:
        consumer = AIOKafkaConsumer(
            ENRICHED_TOPIC, bootstrap_servers=KAFKA_BOOTSTRAP, group_id="topology-service"
        )
        try:
            await consumer.start()
            async for msg in consumer:
                with contextlib.suppress(json.JSONDecodeError, UnicodeDecodeError, TypeError):
                    alarm = json.loads(msg.value) if msg.value else None
                    if isinstance(alarm, dict) and state["ready"]:
                        await graph.add_alarm(alarm)
                        state["alarms"] += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Kafka error: %s. Retrying in 3s", type(exc).__name__)
            await asyncio.sleep(3)
        finally:
            with contextlib.suppress(Exception):
                await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    tasks = [asyncio.create_task(init_graph())]
    if not DISABLE_KAFKA:
        tasks.append(asyncio.create_task(consume_alarms()))
    yield
    for t in tasks:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    with contextlib.suppress(Exception):
        await graph.close()


app = FastAPI(title="NetSentinel topology-service", version="0.1.0", lifespan=lifespan)


def _require_ready() -> None:
    if not state["ready"]:
        raise HTTPException(status_code=503, detail="Graph not ready")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    if state["ready"]:
        return {"status": "ready", "backend": graph.kind}
    response.status_code = 503
    return {"status": "not ready", "error": state["error"]}


@app.get("/graph/summary")
async def summary() -> dict[str, Any]:
    _require_ready()
    return {"backend": graph.kind, "counts": await graph.summary()}


@app.get("/graph/impact")
async def impact(
    linkId: str | None = None,  # noqa: N803 - API uses camelCase
    siteId: str | None = None,  # noqa: N803
    nodeId: str | None = None,  # noqa: N803
) -> dict[str, Any]:
    """Which cells lose service if this link, site or node fails?"""
    _require_ready()
    given = [(t, v) for t, v in (("link", linkId), ("site", siteId), ("node", nodeId)) if v]
    if len(given) != 1:
        raise HTTPException(status_code=400, detail="Give exactly one of linkId, siteId, nodeId")
    target_type, target_id = given[0]
    if not ID_RE[target_type].match(target_id):
        raise HTTPException(status_code=400, detail=f"Invalid {target_type} id")
    tt: TargetType = target_type  # type: ignore[assignment]
    try:
        result = await graph.impact(tt, target_id)
    except UnknownTarget as exc:
        raise HTTPException(status_code=404, detail=f"Unknown {target_type} {exc}") from exc
    return result.to_dict()


@app.get("/graph/context/{entity_id}")
async def context(entity_id: str) -> dict[str, Any]:
    """Step 15: one-hop neighbourhood of a site, link, node or cell (Graph RAG expansion)."""
    _require_ready()
    if entity_type(entity_id) is None:
        raise HTTPException(status_code=400, detail="expected SITE-xxx, LNK-xxx, a node or cell id")
    try:
        ctx = await graph.context(entity_id)
    except UnknownTarget as exc:
        raise HTTPException(status_code=404, detail=f"unknown {entity_id}") from exc
    return {**ctx, "backend": graph.kind}


@app.get("/graph/queries")
async def list_queries() -> dict[str, Any]:
    return {"items": queries.describe()}


@app.post("/graph/queries/{name}")
async def run_query(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one catalogue query by name with parameters (never free-form Cypher)."""
    _require_ready()
    if name not in queries.CATALOGUE:
        raise HTTPException(status_code=404, detail="Unknown query")
    p = dict(params or {})
    if "hops" in p:
        p["hops"] = max(1, min(int(p["hops"]), 4))
    if "limit" in p:
        p["limit"] = max(1, min(int(p["limit"]), 100))
    try:
        rows = await graph.run_named(name, p)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"name": name, "rows": rows[:500]}


@app.post("/graph/reload")
async def reload() -> dict[str, Any]:
    """Re-load the topology and runbooks (MERGE; idempotent). Admin-only at the gateway."""
    _require_ready()
    topo = resolve_topology(TOPOLOGY_FILE, TOPOLOGY_SEED, TOPOLOGY_FULL)
    runbooks = read_runbooks(RUNBOOKS_DIR) if os.path.isdir(RUNBOOKS_DIR) else []
    state["loaded"] = await graph.load(topo, runbooks)
    return {"loaded": state["loaded"], "backend": graph.kind}


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8008")))
