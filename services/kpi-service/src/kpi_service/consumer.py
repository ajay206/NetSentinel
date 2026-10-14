from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer

from .models import KpiRow, parse_sample
from .store import MemoryStore, PgStore

logger = logging.getLogger(__name__)

Store = MemoryStore | PgStore


class BatchWriter:
    def __init__(
        self,
        store: Store,
        max_batch: int = 500,
        max_wait: float = 1.0,
    ) -> None:
        self._store = store
        self._max_batch = max_batch
        self._max_wait = max_wait
        self._buffer: list[KpiRow] = []
        self._lock = asyncio.Lock()
        self._stats = {"received": 0, "written": 0, "invalid": 0}
        self._flush_task: asyncio.Task[None] | None = None

    async def add(self, raw: dict[str, Any]) -> None:
        self._stats["received"] += 1
        row = parse_sample(raw)
        if row is None:
            self._stats["invalid"] += 1
            return
        async with self._lock:
            self._buffer.append(row)
            if len(self._buffer) >= self._max_batch:
                await self._flush_locked()

    async def flush(self, raise_on_error: bool = False) -> int:
        async with self._lock:
            return await self._flush_locked(raise_on_error)

    async def _flush_locked(self, raise_on_error: bool = False) -> int:
        if not self._buffer:
            return 0
        batch = self._buffer
        self._buffer = []
        try:
            written = await self._store.insert_many(batch)
            self._stats["written"] += written
            return written
        except Exception:
            logger.exception("Failed to write batch")
            self._buffer = batch + self._buffer
            if raise_on_error:
                raise
            return 0

    def stats(self) -> dict[str, int]:
        return dict(self._stats)


async def consume_forever(
    store: Store,
    writer: BatchWriter,
    bootstrap: str,
    topic: str,
    state: dict[str, Any],
) -> None:
    """Consume KPI samples; commit offsets only after the batch is in the store.

    At-least-once: a crash before commit replays the batch, and inserts are idempotent
    (ON CONFLICT (cell_id, ts) DO NOTHING). See ADR-005.
    """
    while True:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap,
            group_id="kpi-service",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            max_poll_records=500,
        )
        try:
            await consumer.start()
            state["connected"] = True
            logger.info("Kafka consumer started on %s", topic)
            while True:
                batches = await consumer.getmany(timeout_ms=1000, max_records=500)
                if not batches:
                    continue
                for records in batches.values():
                    for record in records:
                        try:
                            raw = json.loads(record.value) if record.value else None
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            raw = None
                        await writer.add(raw if isinstance(raw, dict) else {})
                await writer.flush(raise_on_error=True)
                await consumer.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("KPI consumer error, reconnecting in 3s")
        finally:
            state["connected"] = False
            with contextlib.suppress(Exception):
                await consumer.stop()
        await asyncio.sleep(3)
