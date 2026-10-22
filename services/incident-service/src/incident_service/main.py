"""incident-service (W13): alarms.enriched -> topology-aware clustering -> incidents.

State is in memory and rebuilt on start by re-reading ``alarms.enriched`` from the beginning
(no consumer group), so a restart replays the same alarms in the same order and yields the same
incidents. Every incident change is published to ``incidents`` keyed by incident id (the topic is
a changelog: the latest ``version`` per key wins). See ADR-012.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI, Header, HTTPException, Query, Response
from netgen import build_topology

from .clustering import IncidentClusterer, compression_ratio
from .workflow import (
    ACTOR_RE,
    WRITE_ROLES,
    ActionError,
    AlarmAction,
    IncidentAction,
    WorkflowStore,
    apply,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("incident-service")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
ENRICHED_TOPIC = os.getenv("ENRICHED_TOPIC", "alarms.enriched")
INCIDENTS_TOPIC = os.getenv("INCIDENTS_TOPIC", "incidents")
DISABLE_KAFKA = os.getenv("DISABLE_KAFKA", "0") == "1"
TOPOLOGY_SEED = int(os.getenv("TOPOLOGY_SEED", "42"))
TOPOLOGY_FULL = os.getenv("TOPOLOGY_FULL", "0") == "1"
GAP_SECONDS = int(os.getenv("INCIDENT_GAP_SECONDS", "300"))
MAX_HOPS = int(os.getenv("INCIDENT_MAX_HOPS", "4"))
MAX_INCIDENTS = int(os.getenv("INCIDENT_MAX_KEEP", "500"))

clusterer = IncidentClusterer(
    build_topology(seed=TOPOLOGY_SEED, small=not TOPOLOGY_FULL),
    gap_seconds=GAP_SECONDS,
    max_hops=MAX_HOPS,
)
state: dict[str, Any] = {"connected": False, "published": 0}
workflow = WorkflowStore()


def prune(max_keep: int = MAX_INCIDENTS) -> None:
    """Bound memory: once over ``max_keep``, drop the oldest incidents down to 90% of it.

    The alarm-id index is pruned too, and the 10% headroom avoids a sort on every message.
    """
    if len(clusterer.incidents) <= max_keep:
        return
    extra = len(clusterer.incidents) - int(max_keep * 0.9)
    oldest = sorted(clusterer.incidents.values(), key=lambda i: (i.last_seen, i.id))
    for inc in oldest[:extra]:
        for aid in inc.alarm_ids:
            clusterer._alarm_incident.pop(aid, None)
        del clusterer.incidents[inc.id]


def handle(alarm: Any) -> dict[str, Any] | None:
    """Cluster one enriched alarm; returns the changed incident as JSON, if any."""
    if not isinstance(alarm, dict):
        return None
    inc = clusterer.add(alarm)
    if inc is None:
        return None
    prune()
    return inc.to_dict()


async def consume_forever() -> None:
    while True:
        consumer = AIOKafkaConsumer(
            ENRICHED_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=None,  # replay from the start on every boot (deterministic state)
            auto_offset_reset="earliest",
        )
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, acks="all")
        try:
            await producer.start()
            await consumer.start()
            state["connected"] = True
            logger.info("Clustering %s -> %s", ENRICHED_TOPIC, INCIDENTS_TOPIC)
            async for msg in consumer:
                try:
                    alarm = json.loads(msg.value) if msg.value else None
                except (json.JSONDecodeError, UnicodeDecodeError):
                    alarm = None
                incident = handle(alarm)
                if incident is not None:
                    await producer.send_and_wait(
                        INCIDENTS_TOPIC,
                        value=json.dumps(incident).encode(),
                        key=incident["id"].encode(),
                    )
                    state["published"] += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Kafka error: %s. Retrying in 3s", exc)
            await asyncio.sleep(3)
        finally:
            state["connected"] = False
            with contextlib.suppress(Exception):
                await consumer.stop()
            with contextlib.suppress(Exception):
                await producer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = None if DISABLE_KAFKA else asyncio.create_task(consume_forever())
    yield
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="NetSentinel incident-service", version="0.1.0", lifespan=lifespan)


def _stats() -> dict[str, Any]:
    alarms = sum(len(i.alarm_ids) for i in clusterer.incidents.values())
    incidents = len(clusterer.incidents)
    return {
        "alarms": alarms,
        "incidents": incidents,
        "compressionRatio": round(compression_ratio(alarms, incidents), 2),
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(response: Response) -> dict[str, str]:
    if DISABLE_KAFKA or state["connected"]:
        return {"status": "ready"}
    response.status_code = 503
    return {"status": "not ready"}


@app.get("/incidents")
async def list_incidents(
    status: Literal["open", "cleared"] | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    items = [i for i in clusterer.snapshot() if status is None or i["status"] == status]
    return {"items": [_with_wf(i) for i in items[:limit]], "total": len(items), "stats": _stats()}


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict[str, Any]:
    inc = clusterer.incidents.get(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _with_wf(inc.to_dict())


def _with_wf(item: dict[str, Any]) -> dict[str, Any]:
    wf = workflow.incidents.get(item["id"])
    return {**item, "workflow": wf}


def _actor(user: str | None, role: str | None, token: str | None = None) -> str:
    """The gateway forwards the signed-in user; only operator/admin may write.

    With ``INCIDENT_SERVICE_TOKEN`` set, callers must also send ``X-NS-Internal-Token``
    (the gateway does), so the user/role headers cannot be forged from outside.
    """
    expected = os.getenv("INCIDENT_SERVICE_TOKEN")
    if expected and not hmac.compare_digest((token or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="missing or invalid internal token")
    if role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Requires role operator")
    if not user or not ACTOR_RE.match(user):
        raise HTTPException(status_code=400, detail="Missing or invalid actor")
    return user


@app.post("/incidents/{incident_id}/actions")
async def incident_action(
    incident_id: str,
    req: IncidentAction,
    x_ns_user: str | None = Header(default=None),
    x_ns_role: str | None = Header(default=None),
    x_ns_internal_token: str | None = Header(default=None),
) -> dict[str, Any]:
    actor = _actor(x_ns_user, x_ns_role, x_ns_internal_token)
    inc = clusterer.incidents.get(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    try:
        apply(workflow.incident(incident_id), req.action, actor, req.note, req.assignee)
    except ActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _with_wf(inc.to_dict())


@app.post("/alarms/actions")
async def alarm_action(
    req: AlarmAction,
    x_ns_user: str | None = Header(default=None),
    x_ns_role: str | None = Header(default=None),
    x_ns_internal_token: str | None = Header(default=None),
) -> dict[str, Any]:
    actor = _actor(x_ns_user, x_ns_role, x_ns_internal_token)
    try:
        wf = apply(workflow.alarm(req.key), req.action, actor, req.note)
    except ActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"key": req.key, "workflow": wf}


@app.get("/alarms/workflow")
async def alarm_workflow() -> dict[str, Any]:
    return {"items": workflow.alarms}


@app.get("/stats")
async def stats() -> dict[str, Any]:
    return {
        **_stats(),
        "alarmsSeen": clusterer.alarms_seen,
        "published": state["published"],
        "gapSeconds": GAP_SECONDS,
        "maxHops": MAX_HOPS,
    }


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8007")))
