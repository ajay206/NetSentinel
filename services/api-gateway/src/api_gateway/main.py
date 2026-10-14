"""FastAPI application for NetSentinel API Gateway.

ADR-003: Week 2 - No auth, local only. Auth and multi-tenancy deferred.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import statistics
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# netgen is a workspace dependency
from netgen import build_topology

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint with dependency status."""
    kafka_status, timescale_status = await asyncio.gather(check_kafka(), check_timescaledb())

    services = [
        {"name": "api-gateway", "status": "up"},
        kafka_status,
        timescale_status,
    ]

    overall = "ok" if all(s["status"] == "up" for s in services[1:]) else "degraded"

    return JSONResponse(
        {
            "status": overall,
            "services": services,
            "checkedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
    )


@app.get("/api/alarms/recent")
async def recent_alarms() -> JSONResponse:
    """Return recent alarms."""
    return JSONResponse(hub.get_snapshot())


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
