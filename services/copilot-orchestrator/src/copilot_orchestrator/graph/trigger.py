"""W17: start a multi-agent run on ``incident.created`` (first sighting on the incidents topic).

incident-service republishes an incident every time it grows; only the first message for an id
(version 1, or an id this process has not seen) counts as "created". Opt-in: AGENT_TRIGGER=kafka.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)
INC_RE = re.compile(r"^INC-[0-9A-F]{10}$")
SITE_RE = re.compile(r"^SITE-\d{3}$")


class Seen(OrderedDict):
    def __init__(self, cap: int = 5000) -> None:
        super().__init__()
        self.cap = cap

    def add(self, key: str) -> None:
        self[key] = True
        if len(self) > self.cap:
            self.popitem(last=False)


def created(incident: Any, seen: Seen) -> tuple[str, str] | None:
    """(incident_id, root_site) if this message is an incident.created event, else None."""
    if not isinstance(incident, dict):
        return None
    iid, site = str(incident.get("id", "")), str(incident.get("rootSiteId", ""))
    if not INC_RE.match(iid) or not SITE_RE.match(site) or iid in seen:
        return None
    seen.add(iid)
    if int(incident.get("version", 1) or 1) > 1:
        return None  # an update to an incident that predates this process
    return iid, site


async def consume(service: Any) -> None:  # pragma: no cover - needs Kafka
    from aiokafka import AIOKafkaConsumer

    topic = os.getenv("INCIDENTS_TOPIC", "incidents")
    seen = Seen()
    while True:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
            group_id="copilot-agents",
            auto_offset_reset="latest",
        )
        try:
            await consumer.start()
            logger.info("agent trigger: consuming %s", topic)
            async for msg in consumer:
                try:
                    hit = created(json.loads(msg.value or b"null"), seen)
                except (ValueError, UnicodeDecodeError):
                    hit = None
                if hit:
                    run = await service.start(hit[1], hit[0], trigger="incident.created")
                    logger.info(
                        "incident.created %s -> %s (%s)", hit[0], run["runId"], run["status"]
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep retrying while Kafka comes up
            logger.warning("agent trigger error: %s; retrying in 5s", type(exc).__name__)
            await asyncio.sleep(5)
        finally:
            await consumer.stop()
