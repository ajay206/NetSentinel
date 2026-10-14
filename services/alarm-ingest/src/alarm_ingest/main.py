"""alarm-ingest service: alarms.raw -> normalise/enrich/dedupe/correlate -> alarms.enriched.

Delivery is at-least-once: the consumer offset is committed only after the enriched
alarm has been acknowledged by Kafka (acks=all). See ADR-004.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI, Response
from netgen import build_topology

from .pipeline import Pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("alarm-ingest")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
RAW_TOPIC = os.getenv("RAW_TOPIC", "alarms.raw")
ENRICHED_TOPIC = os.getenv("ENRICHED_TOPIC", "alarms.enriched")
DISABLE_KAFKA = os.getenv("DISABLE_KAFKA", "0") == "1"
TOPOLOGY_SEED = int(os.getenv("TOPOLOGY_SEED", "42"))
TOPOLOGY_FULL = os.getenv("TOPOLOGY_FULL", "0") == "1"

pipeline = Pipeline(build_topology(seed=TOPOLOGY_SEED, small=not TOPOLOGY_FULL))
state: dict[str, bool] = {"connected": False}


async def consume_forever() -> None:
    """Consume raw alarms and publish enriched ones, reconnecting on errors."""
    while True:
        consumer = AIOKafkaConsumer(
            RAW_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id="alarm-ingest",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, acks="all")
        try:
            await producer.start()
            await consumer.start()
            state["connected"] = True
            logger.info("Consuming %s -> %s", RAW_TOPIC, ENRICHED_TOPIC)
            async for msg in consumer:
                try:
                    raw = json.loads(msg.value) if msg.value else None
                except (json.JSONDecodeError, UnicodeDecodeError):
                    raw = None
                if isinstance(raw, dict):
                    enriched = pipeline.handle(raw)
                else:
                    enriched = None
                    pipeline.stats["received"] += 1
                    pipeline.stats["invalid"] += 1
                if enriched is not None:
                    await producer.send_and_wait(
                        ENRICHED_TOPIC,
                        value=json.dumps(enriched).encode(),
                        key=str(enriched.get("siteId", "")).encode(),
                    )
                await consumer.commit()
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


app = FastAPI(title="NetSentinel alarm-ingest", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(response: Response) -> dict[str, str]:
    if DISABLE_KAFKA or state["connected"]:
        return {"status": "ready"}
    response.status_code = 503
    return {"status": "not ready"}


@app.get("/stats")
async def stats() -> dict[str, Any]:
    return {**pipeline.stats, "activeDedupKeys": pipeline.active_dedup_keys}


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))
