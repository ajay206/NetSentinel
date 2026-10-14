"""FastAPI application for NetSentinel API Gateway.

ADR-003: Week 2 - No auth, local only. Auth and multi-tenancy deferred.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("api-gateway")

# Settings from environment
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
ALARM_TOPIC = os.getenv("ALARM_TOPIC", "alarms.raw")
TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "localhost")
TIMESCALE_PORT = int(os.getenv("TIMESCALE_PORT", "5432"))
CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]
DISABLE_KAFKA = os.getenv("DISABLE_KAFKA", "0") == "1"


class AlarmHub:
    """Manages WebSocket clients and recent alarm buffer."""

    def __init__(self, maxlen: int = 200) -> None:
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
        message = json.dumps({"type": "alarm", "alarm": alarm}, default=str)
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


async def kafka_consumer_task() -> None:
    """Background task consuming alarms from Kafka and publishing to hub."""
    while True:
        consumer: AIOKafkaConsumer | None = None
        try:
            consumer = AIOKafkaConsumer(
                ALARM_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=None,
                auto_offset_reset="latest",
            )
            await consumer.start()
            logger.info("Kafka consumer started on topic %s", ALARM_TOPIC)
            async for msg in consumer:
                try:
                    alarm = json.loads(msg.value)
                    if isinstance(alarm, dict):
                        await hub.publish(alarm)
                    else:
                        logger.warning("Skipping non-dict message: %s", type(alarm))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.warning("Skipping invalid JSON message")
                except Exception as e:
                    logger.exception("Error processing message: %s", e)
        except Exception as e:
            logger.warning("Kafka consumer error: %s. Retrying in 3s...", e)
            await asyncio.sleep(3)
        finally:
            if consumer is not None:
                with contextlib.suppress(Exception):
                    await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    consumer_task: asyncio.Task | None = None
    if not DISABLE_KAFKA:
        consumer_task = asyncio.create_task(kafka_consumer_task())
        logger.info("Kafka consumer task started")
    else:
        logger.info("Kafka disabled via DISABLE_KAFKA=1")
    yield
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    logger.info("Application shutdown complete")


app = FastAPI(
    title="NetSentinel API Gateway",
    description="Real-time alarm streaming and query API",
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


@app.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time alarm streaming."""
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
