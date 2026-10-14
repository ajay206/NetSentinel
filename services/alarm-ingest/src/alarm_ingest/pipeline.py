from __future__ import annotations

import datetime as dt
import time
from collections.abc import Callable
from typing import Any

from netgen import Topology

from .correlate import Correlator
from .dedupe import Deduper
from .enrich import Enricher
from .normalize import InvalidAlarm, normalize


class Pipeline:
    """Processing pipeline: normalize -> enrich -> dedupe -> correlate."""

    def __init__(
        self,
        topology: Topology,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._enricher = Enricher(topology)
        self._deduper = Deduper(clock=clock)
        self._correlator = Correlator(topology, clock=clock)
        self._clock = clock
        self.stats = {
            "received": 0,
            "published": 0,
            "invalid": 0,
            "duplicates": 0,
        }

    def handle(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """Process a raw alarm, return enriched alarm or None if invalid."""
        self.stats["received"] += 1
        try:
            normalized = normalize(raw)
        except InvalidAlarm:
            self.stats["invalid"] += 1
            return None

        enriched = self._enricher.enrich(normalized)
        deduped = self._deduper.process(enriched)
        correlated = self._correlator.correlate(deduped)

        # Add ingestedAt and @type
        now_utc = dt.datetime.now(dt.UTC)
        ingested_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        correlated["ingestedAt"] = ingested_at
        correlated["@type"] = "EnrichedAlarm"

        if deduped.get("dedup", {}).get("isDuplicate"):
            self.stats["duplicates"] += 1
        self.stats["published"] += 1

        return correlated

    @property
    def active_dedup_keys(self) -> int:
        return self._deduper.active_count
