"""FastAPI application for NetSentinel API Gateway.

ADR-003: Week 2 - No auth, local only. Auth and multi-tenancy deferred.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import statistics
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# netgen is a workspace dependency
from netgen import build_topology

from api_gateway.auth import AuthMiddleware
from api_gateway.auth import router as auth_router
from api_gateway.timeline import build_timeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("api-gateway")

# Settings from environment
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
ALARM_TOPIC = os.getenv("ALARM_TOPIC", "alarms.raw")
KPI_TOPIC = os.getenv("KPI_TOPIC", "kpis")
ENRICHED_TOPIC = os.getenv("ENRICHED_TOPIC", "alarms.enriched")
TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "localhost")
TIMESCALE_PORT = int(os.getenv("TIMESCALE_PORT", "5432"))
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]
DISABLE_KAFKA = os.getenv("DISABLE_KAFKA", "0") == "1"
KPI_SERVICE_URL = os.getenv("KPI_SERVICE_URL", "http://localhost:8002").rstrip("/")
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8003").rstrip("/")
COPILOT_URL = os.getenv("COPILOT_URL", "http://localhost:8005").rstrip("/")
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8004").rstrip("/")
ALARM_INGEST_URL = os.getenv("ALARM_INGEST_URL", "http://localhost:8001").rstrip("/")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8006").rstrip("/")
INCIDENT_SERVICE_URL = os.getenv("INCIDENT_SERVICE_URL", "http://localhost:8007").rstrip("/")
# W11: Phase 1 services probed through the gateway for the health panel
PHASE1_SERVICES = {
    "alarm-ingest": lambda: ALARM_INGEST_URL,
    "kpi-service": lambda: KPI_SERVICE_URL,
    "ml-service": lambda: ML_SERVICE_URL,
    "rag-service": lambda: RAG_SERVICE_URL,
    "copilot-orchestrator": lambda: COPILOT_URL,
    "mcp-server": lambda: MCP_SERVER_URL,
    "incident-service": lambda: INCIDENT_SERVICE_URL,
}
health_transport: httpx.AsyncBaseTransport | None = None
# Tests swap this for an httpx.MockTransport
kpi_transport: httpx.AsyncBaseTransport | None = None
ml_transport: httpx.AsyncBaseTransport | None = None
rag_transport: httpx.AsyncBaseTransport | None = None
copilot_transport: httpx.AsyncBaseTransport | None = None
incident_transport: httpx.AsyncBaseTransport | None = None

# Topology generation settings
TOPOLOGY_SEED = int(os.getenv("TOPOLOGY_SEED", "42"))
TOPOLOGY_FULL = os.getenv("TOPOLOGY_FULL", "0") == "1"

# Build topology once at import
topology = build_topology(seed=TOPOLOGY_SEED, small=not TOPOLOGY_FULL)


class AlarmHub:
    """Manages WebSocket clients and recent alarm buffer."""

    def __init__(self, maxlen: int = 200, message_type: str = "alarm") -> None:
        self.message_type = message_type
        self.clients: set[WebSocket] = set()
        self.recent: deque[dict[str, Any]] = deque(maxlen=maxlen)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clients.add(websocket)
        logger.info("WebSocket connected. Total clients: %d", len(self.clients))

    def disconnect(self, websocket: WebSocket) -> None:
        self.clients.discard(websocket)
        logger.info("WebSocket disconnected. Total clients: %d", len(self.clients))

    async def publish(self, alarm: dict[str, Any]) -> None:
        """Broadcast alarm to all connected clients."""
        self.recent.append(alarm)
        message = json.dumps({"type": self.message_type, "alarm": alarm}, default=str)
        dead_clients: list[WebSocket] = []
        for client in self.clients:
            try:
                await client.send_text(message)
            except Exception:
                dead_clients.append(client)
        for client in dead_clients:
            self.disconnect(client)

    def get_snapshot(self) -> list[dict[str, Any]]:
        """Return recent alarms as list."""
        return list(self.recent)


hub = AlarmHub()
enriched_hub = AlarmHub(message_type="enriched")
# W11: slim (time, severity) history for the storm timeline; longer than the 200-alarm buffer
timeline_events: deque[dict[str, Any]] = deque(maxlen=5000)


class KpiActivity:
    """Tracks KPI samples and computes rolling statistics."""

    def __init__(self, window_seconds: int = 60, rolling_maxlen: int = 500) -> None:
        self.total_samples = 0
        self._arrival_times: deque[float] = deque()  # monotonic timestamps
        self._window_seconds = window_seconds
        self._last_sample: dict[str, Any] | None = None
        self._last_timestamp: str | None = None
        # per-KPI rolling window of values for average computation
        self._kpi_values: dict[str, deque[float]] = {}
        self._rolling_maxlen = rolling_maxlen
        # track cellIds in rolling window
        self._cell_ids: deque[str] = deque(maxlen=rolling_maxlen)

    def record(self, sample: dict[str, Any]) -> None:
        """Record a KPI sample. Expected keys: cellId, kpis (dict), timestamp."""
        now = time.monotonic()
        self.total_samples += 1
        self._arrival_times.append(now)
        self._last_sample = sample
        self._last_timestamp = sample.get("timestamp") or datetime.now(UTC).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")

        # Extract cellId for distinct count
        cell_id = sample.get("cellId")
        if cell_id is not None:
            self._cell_ids.append(str(cell_id))

        # Extract KPI name and value
        kpis = sample.get("kpis", {})
        if isinstance(kpis, dict):
            for kpi_name, value in kpis.items():
                if isinstance(value, (int, float)):
                    if kpi_name not in self._kpi_values:
                        self._kpi_values[kpi_name] = deque(maxlen=self._rolling_maxlen)
                    self._kpi_values[kpi_name].append(float(value))

        # Prune arrival times older than window
        cutoff = now - self._window_seconds
        while self._arrival_times and self._arrival_times[0] < cutoff:
            self._arrival_times.popleft()

    def snapshot(self) -> dict[str, Any]:
        """Return current activity snapshot."""
        rate_per_min = (
            len(self._arrival_times) * 60.0 / self._window_seconds
            if self._window_seconds > 0
            else 0.0
        )

        averages: dict[str, float] = {}
        for kpi, values in self._kpi_values.items():
            if values:
                averages[kpi] = round(statistics.mean(values), 3)

        cells_reporting = len(set(self._cell_ids))

        return {
            "totalSamples": self.total_samples,
            "ratePerMin": round(rate_per_min, 2),
            "lastSampleTime": self._last_timestamp
            or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "lastSample": self._last_sample,
            "averages": averages,
            "cellsReporting": cells_reporting,
        }


kpi_activity = KpiActivity()


async def tcp_check(host: str, port: int, timeout: float = 1.5) -> bool:
    """Check TCP connectivity to host:port."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        return True
    except Exception:
        return False


async def check_kafka() -> dict[str, Any]:
    """Check Kafka connectivity (first bootstrap server)."""
    first_bootstrap = KAFKA_BOOTSTRAP.split(",")[0].strip()
    if ":" not in first_bootstrap:
        return {"name": "kafka", "status": "down", "detail": "Invalid bootstrap format"}
    host, port_str = first_bootstrap.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError:
        return {"name": "kafka", "status": "down", "detail": "Invalid port"}
    ok = await tcp_check(host, port)
    return {
        "name": "kafka",
        "status": "up" if ok else "down",
        "detail": f"{host}:{port}" if ok else f"Connection failed to {host}:{port}",
    }


async def check_timescaledb() -> dict[str, Any]:
    """Check TimescaleDB connectivity."""
    ok = await tcp_check(TIMESCALE_HOST, TIMESCALE_PORT)
    return {
        "name": "timescaledb",
        "status": "up" if ok else "down",
        "detail": f"{TIMESCALE_HOST}:{TIMESCALE_PORT}" if ok else "Connection failed",
    }


async def consume_topic(topic: str, handler: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
    """Generic Kafka consumer with retry logic."""
    while True:
        consumer: AIOKafkaConsumer | None = None
        try:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=None,
                auto_offset_reset="latest",
            )
            await consumer.start()
            logger.info("Kafka consumer started on topic %s", topic)
            async for msg in consumer:
                try:
                    data = json.loads(msg.value)
                    if isinstance(data, dict):
                        await handler(data)
                    else:
                        logger.warning("Skipping non-dict message on %s: %s", topic, type(data))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.warning("Skipping invalid JSON message on %s", topic)
                except Exception as e:
                    logger.exception("Error processing message on %s: %s", topic, e)
        except Exception as e:
            logger.warning("Kafka consumer error on %s: %s. Retrying in 3s...", topic, e)
            await asyncio.sleep(3)
        finally:
            if consumer is not None:
                with contextlib.suppress(Exception):
                    await consumer.stop()


async def alarm_handler(alarm: dict[str, Any]) -> None:
    await hub.publish(alarm)


async def enriched_handler(alarm: dict[str, Any]) -> None:
    timeline_events.append(
        {
            "alarmRaisedTime": alarm.get("alarmRaisedTime"),
            "perceivedSeverity": alarm.get("perceivedSeverity"),
        }
    )
    await enriched_hub.publish(alarm)


async def kpi_handler(sample: dict[str, Any]) -> None:
    kpi_activity.record(sample)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    consumer_tasks: list[asyncio.Task] = []
    if not DISABLE_KAFKA:
        consumer_tasks.append(asyncio.create_task(consume_topic(ALARM_TOPIC, alarm_handler)))
        consumer_tasks.append(asyncio.create_task(consume_topic(KPI_TOPIC, kpi_handler)))
        consumer_tasks.append(asyncio.create_task(consume_topic(ENRICHED_TOPIC, enriched_handler)))
        logger.info("Kafka consumers started: %s, %s, %s", ALARM_TOPIC, KPI_TOPIC, ENRICHED_TOPIC)
    else:
        logger.info("Kafka disabled via DISABLE_KAFKA=1")
    yield
    for task in consumer_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Application shutdown complete")


app = FastAPI(
    title="NetSentinel API Gateway",
    description="Real-time alarm streaming, KPI activity, and topology query API",
    version="0.1.0",
    lifespan=lifespan,
)

# W11: auth first so CORS (added last = outermost) also decorates 401/403/429 responses
app.include_router(auth_router)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def check_http_service(name: str, base_url: str) -> dict[str, Any]:
    """GET <service>/healthz with a short timeout; any failure reports the service as down."""
    try:
        async with httpx.AsyncClient(transport=health_transport, timeout=1.5) as client:
            resp = await client.get(f"{base_url}/healthz")
        if resp.status_code == 200:
            return {"name": name, "status": "up", "tier": "phase1"}
        return {
            "name": name,
            "status": "down",
            "detail": f"HTTP {resp.status_code}",
            "tier": "phase1",
        }
    except httpx.HTTPError:
        return {"name": name, "status": "down", "detail": "unreachable", "tier": "phase1"}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """W12 liveness: the process is up (public, no dependency checks)."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> JSONResponse:
    """W12 readiness: Kafka reachable (unless DISABLE_KAFKA) and topology loaded."""
    kafka = {"status": "skipped"} if DISABLE_KAFKA else await check_kafka()
    ready = kafka["status"] in ("up", "skipped") and bool(topology)
    body = {
        "status": "ready" if ready else "not_ready",
        "kafka": kafka["status"],
        "topology": "loaded" if topology else "missing",
    }
    return JSONResponse(body, status_code=200 if ready else 503)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check: core dependencies decide the overall status; Phase 1 services are listed."""
    kafka_status, timescale_status, *phase1 = await asyncio.gather(
        check_kafka(),
        check_timescaledb(),
        *(check_http_service(n, url()) for n, url in PHASE1_SERVICES.items()),
    )

    core = [
        {"name": "api-gateway", "status": "up", "tier": "core"},
        {**kafka_status, "tier": "core"},
        {**timescale_status, "tier": "core"},
    ]
    overall = "ok" if all(s["status"] == "up" for s in core[1:]) else "degraded"

    return JSONResponse(
        {
            "status": overall,
            "services": core + list(phase1),
            "checkedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
    )


@app.get("/api/alarms/recent")
async def recent_alarms() -> JSONResponse:
    """Return recent alarms."""
    return JSONResponse(hub.get_snapshot())


@app.get("/api/alarms/timeline")
async def alarm_timeline(bucketSeconds: int = 60) -> JSONResponse:  # noqa: N803 (API casing)
    """W11: alarm-storm timeline (counts per bucket and severity) over recent enriched alarms."""
    if not 10 <= bucketSeconds <= 3600:
        return JSONResponse({"detail": "bucketSeconds must be 10..3600"}, status_code=422)
    return JSONResponse(build_timeline(list(timeline_events), bucket_seconds=bucketSeconds))


@app.get("/api/alarms/enriched/recent")
async def recent_enriched_alarms() -> JSONResponse:
    """Return recent enriched alarms (from alarm-ingest via alarms.enriched)."""
    return JSONResponse(enriched_hub.get_snapshot())


async def _serve_hub(websocket: WebSocket, hub: AlarmHub) -> None:
    await hub.connect(websocket)
    try:
        # Send snapshot
        snapshot = hub.get_snapshot()
        await websocket.send_text(json.dumps({"type": "snapshot", "alarms": snapshot}, default=str))
        # Keep alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
    finally:
        hub.disconnect(websocket)


@app.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time raw alarm streaming."""
    await _serve_hub(websocket, hub)


@app.websocket("/ws/enriched")
async def websocket_enriched(websocket: WebSocket) -> None:
    """WebSocket endpoint for enriched alarms (snapshot, then type=enriched messages)."""
    await _serve_hub(websocket, enriched_hub)


@app.get("/api/topology")
async def get_topology() -> JSONResponse:
    """Return the generated network topology."""
    return JSONResponse(topology.to_dict())


@app.get("/api/kpis/activity")
async def kpis_activity() -> JSONResponse:
    """Return KPI activity snapshot."""
    return JSONResponse(kpi_activity.snapshot())


@app.websocket("/ws/kpis")
async def websocket_kpis(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time KPI activity streaming."""
    await websocket.accept()
    try:
        while True:
            snapshot = kpi_activity.snapshot()
            message = json.dumps({"type": "kpiActivity", **snapshot}, default=str)
            await websocket.send_text(message)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("WebSocket KPI error: %s", e)


@app.get("/api/kpi/{path:path}")
async def kpi_proxy(path: str, request: Request) -> JSONResponse:
    """Forward read-only KPI queries to kpi-service (W5): /api/kpi/cells, /api/kpi/cells/{id}."""
    if not re.fullmatch(r"cells(/[A-Za-z0-9_.\-]+)?", path) or ".." in path:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    url = f"{KPI_SERVICE_URL}/kpis/{path}"
    try:
        async with httpx.AsyncClient(transport=kpi_transport, timeout=5.0) as client:
            resp = await client.get(url, params=request.query_params)
    except httpx.HTTPError as exc:
        logger.warning("kpi-service unreachable: %s", exc)
        return JSONResponse({"detail": "kpi-service unreachable"}, status_code=503)
    try:
        body = resp.json()
    except ValueError:
        return JSONResponse({"detail": "kpi-service returned non-JSON"}, status_code=502)
    return JSONResponse(body, status_code=resp.status_code)


@app.get("/api/ml/{path:path}")
async def ml_proxy(path: str, request: Request) -> JSONResponse:
    """Forward read-only anomaly queries to ml-service (W6): /api/ml/anomalies[/cells/{id}]."""
    if not re.fullmatch(r"anomalies(/cells/[A-Za-z0-9_.\-]+)?", path) or ".." in path:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    try:
        # ml-service scans up to 20 cells, so allow a longer timeout than the KPI proxy
        async with httpx.AsyncClient(transport=ml_transport, timeout=20.0) as client:
            resp = await client.get(f"{ML_SERVICE_URL}/{path}", params=request.query_params)
    except httpx.HTTPError as exc:
        logger.warning("ml-service unreachable: %s", exc)
        return JSONResponse({"detail": "ml-service unreachable"}, status_code=503)
    try:
        body = resp.json()
    except ValueError:
        return JSONResponse({"detail": "ml-service returned non-JSON"}, status_code=502)
    return JSONResponse(body, status_code=resp.status_code)


@app.post("/api/ml/{action}")
async def ml_post_proxy(action: str, request: Request) -> JSONResponse:
    """Forward fault classification calls to ml-service (W7): /api/ml/predict, /api/ml/explain."""
    if action not in ("predict", "explain"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    body = await request.body()
    if len(body) > 64_000:
        return JSONResponse({"detail": "Request too large"}, status_code=413)
    try:
        async with httpx.AsyncClient(transport=ml_transport, timeout=20.0) as client:
            resp = await client.post(
                f"{ML_SERVICE_URL}/{action}",
                content=body,
                params=request.query_params,
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.warning("ml-service unreachable: %s", exc)
        return JSONResponse({"detail": "ml-service unreachable"}, status_code=503)
    try:
        payload = resp.json()
    except ValueError:
        return JSONResponse({"detail": "ml-service returned non-JSON"}, status_code=502)
    return JSONResponse(payload, status_code=resp.status_code)


_RUNBOOK_ID_RE = re.compile(r"^RB-[A-Z]{3}-\d{3}$")


async def _rag_call(method: str, path: str, body: bytes | None = None) -> JSONResponse:
    try:
        async with httpx.AsyncClient(transport=rag_transport, timeout=15.0) as client:
            resp = await client.request(
                method,
                f"{RAG_SERVICE_URL}/{path}",
                content=body,
                headers={"Content-Type": "application/json"} if body is not None else None,
            )
    except httpx.HTTPError as exc:
        logger.warning("rag-service unreachable: %s", exc)
        return JSONResponse({"detail": "rag-service unreachable"}, status_code=503)
    try:
        payload = resp.json()
    except ValueError:
        return JSONResponse({"detail": "rag-service returned non-JSON"}, status_code=502)
    return JSONResponse(payload, status_code=resp.status_code)


@app.post("/api/rag/search")
async def rag_search_proxy(request: Request) -> JSONResponse:
    """Forward runbook search to rag-service (W8)."""
    body = await request.body()
    if len(body) > 16_000:
        return JSONResponse({"detail": "Request too large"}, status_code=413)
    return await _rag_call("POST", "search", body)


@app.get("/api/rag/runbooks/{runbook_id}")
async def rag_runbook_proxy(runbook_id: str) -> JSONResponse:
    """Fetch one runbook's markdown from rag-service (W8). IDs are validated before forwarding."""
    if not _RUNBOOK_ID_RE.match(runbook_id):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return await _rag_call("GET", f"runbooks/{runbook_id}")


@app.post("/api/copilot/analyze")
async def copilot_analyze_proxy(request: Request) -> JSONResponse:
    """Forward an analyze request to copilot-orchestrator (W9). The LLM can be slow: 90 s."""
    body = await request.body()
    if len(body) > 4_000:
        return JSONResponse({"detail": "Request too large"}, status_code=413)
    try:
        async with httpx.AsyncClient(transport=copilot_transport, timeout=90.0) as client:
            resp = await client.post(
                f"{COPILOT_URL}/analyze",
                content=body,
                headers={"Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.warning("copilot-orchestrator unreachable: %s", exc)
        return JSONResponse({"detail": "copilot-orchestrator unreachable"}, status_code=503)
    try:
        payload = resp.json()
    except ValueError:
        return JSONResponse({"detail": "copilot returned non-JSON"}, status_code=502)
    return JSONResponse(payload, status_code=resp.status_code)


_INCIDENT_PATH_RE = re.compile(r"^(incidents(/INC-[0-9A-F]{10})?|stats)$")


@app.get("/api/incidents")
@app.get("/api/incidents/{incident_id}")
async def incidents_proxy(request: Request, incident_id: str | None = None) -> JSONResponse:
    """W13: incident board data from incident-service (viewer role)."""
    path = "incidents" if incident_id is None else f"incidents/{incident_id}"
    if not _INCIDENT_PATH_RE.match(path):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    try:
        async with httpx.AsyncClient(transport=incident_transport, timeout=10.0) as client:
            resp = await client.get(f"{INCIDENT_SERVICE_URL}/{path}", params=request.query_params)
    except httpx.HTTPError as exc:
        logger.warning("incident-service unreachable: %s", exc)
        return JSONResponse({"detail": "incident-service unreachable"}, status_code=503)
    try:
        payload = resp.json()
    except ValueError:
        return JSONResponse({"detail": "incident-service returned non-JSON"}, status_code=502)
    return JSONResponse(payload, status_code=resp.status_code)
