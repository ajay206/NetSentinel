from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class Deduper:
    """Deduplicate alarms within a time window."""

    def __init__(
        self,
        window_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window = window_seconds
        self._clock = clock
        # key -> (count, first_seen_monotonic, first_seen_iso)
        self._entries: dict[str, tuple[int, float, str]] = {}

    def _make_key(self, alarm: dict[str, Any]) -> str:
        site_id = alarm.get("siteId", "")
        alarm_type = alarm.get("alarmType", "")
        probable_cause = alarm.get("probableCause", "")
        specific_problem = alarm.get("specificProblem", "")
        return "|".join([site_id, alarm_type, probable_cause, specific_problem])

    def _prune_expired(self, now: float) -> None:
        expired = [k for k, (_, ts, _) in self._entries.items() if now - ts > self._window]
        for k in expired:
            del self._entries[k]

    def process(self, alarm: dict[str, Any]) -> dict[str, Any]:
        """Process an alarm, returning a copy with dedup info."""
        now = self._clock()
        self._prune_expired(now)

        key = self._make_key(alarm)
        severity = alarm.get("perceivedSeverity")
        state = alarm.get("state")
        raised_time = alarm.get("alarmRaisedTime")

        # Cleared: drop all active keys for this site with the same probableCause
        if severity == "cleared" and state == "cleared":
            site_id = alarm.get("siteId", "")
            probable_cause = alarm.get("probableCause", "")
            # Find keys matching site and probableCause
            to_remove = []
            for k in self._entries:
                parts = k.split("|")
                if len(parts) >= 3 and parts[0] == site_id and parts[2] == probable_cause:
                    to_remove.append(k)
            for k in to_remove:
                del self._entries[k]
            # The clear itself is reported with count 1, isDuplicate False
            dedup_info = {
                "key": key,
                "count": 1,
                "firstSeen": raised_time,
                "isDuplicate": False,
            }
            result = dict(alarm)
            result["dedup"] = dedup_info
            return result

        # Normal processing
        if key in self._entries:
            count, first_ts, first_iso = self._entries[key]
            count += 1
            self._entries[key] = (count, first_ts, first_iso)
            is_duplicate = True
        else:
            count = 1
            first_iso = raised_time
            self._entries[key] = (count, now, first_iso)
            is_duplicate = False

        dedup_info = {
            "key": key,
            "count": count,
            "firstSeen": first_iso,
            "isDuplicate": is_duplicate,
        }
        result = dict(alarm)
        result["dedup"] = dedup_info
        return result

    @property
    def active_count(self) -> int:
        """Return number of active dedup keys (after pruning)."""
        now = self._clock()
        self._prune_expired(now)
        return len(self._entries)
