"""Evidence gathering from the gateway (alarms), ml-service (anomalies, fault) and rag-service."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Any

import httpx

ANOMALY_KPIS = ("dlThroughputMbps", "availabilityPct", "rrcSetupSuccessPct")
_SEVERITY_RANK = {"critical": 0, "major": 1, "minor": 2, "warning": 3, "indeterminate": 4}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def alarm_matches_site(alarm: dict[str, Any], site_id: str) -> bool:
    corr = alarm.get("correlation") or {}
    enr = alarm.get("enrichment") or {}
    return site_id in (alarm.get("siteId"), corr.get("rootSiteId"), enr.get("parentSiteId"))


def select_site_alarms(
    alarms: list[dict[str, Any]], site_id: str, window_minutes: int, limit: int = 20
) -> list[dict[str, Any]]:
    """Alarms for the site (or rooted at it) within ``window_minutes`` of the newest one.

    The window is anchored on the newest matching alarm, not the wall clock, so replayed
    scenarios and demo data still work. Root alarms first, then most severe, then oldest.
    """
    matching = [
        a
        for a in alarms
        if alarm_matches_site(a, site_id) and _parse_ts(a.get("alarmRaisedTime")) is not None
    ]
    if not matching:
        return []
    newest = max(_parse_ts(a["alarmRaisedTime"]) for a in matching)  # type: ignore[type-var]
    since = newest - timedelta(minutes=window_minutes)
    in_window = [a for a in matching if _parse_ts(a["alarmRaisedTime"]) >= since]  # type: ignore[operator]
    in_window.sort(
        key=lambda a: (
            0 if (a.get("correlation") or {}).get("role") == "root" else 1,
            _SEVERITY_RANK.get(str(a.get("perceivedSeverity", "")).lower(), 9),
            a["alarmRaisedTime"],
        )
    )
    return in_window[:limit]


class ToolRecorder:
    """Records one entry per evidence call so the console can show tool-call chips.

    Subclasses implement ``_alarms_for_site`` / ``_anomalies_for_site`` / ``_predict`` /
    ``_runbooks`` and append to ``self.warnings`` on failure.
    """

    transport_name = "http"
    TOOL_NAMES = {
        "alarms_for_site": "get_alarms",
        "anomalies_for_site": "kpi_anomalies",
        "predict": "predict_fault",
        "runbooks": "search_runbooks",
    }

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []

    async def _timed(self, key: str, coro: Any) -> Any:
        before = len(self.warnings)
        t0 = time.perf_counter()
        raised = True
        try:
            result = await coro
            raised = False
            return result
        finally:
            self.tool_calls.append(
                {
                    "name": self.TOOL_NAMES[key],
                    "ok": not raised and len(self.warnings) == before,
                    "durationMs": int((time.perf_counter() - t0) * 1000),
                    "transport": self.transport_name,
                }
            )

    async def alarms_for_site(self, site_id: str, window_minutes: int) -> list[dict[str, Any]]:
        return await self._timed("alarms_for_site", self._alarms_for_site(site_id, window_minutes))

    async def anomalies_for_site(self, site_id: str, hours: int = 1) -> list[dict[str, Any]]:
        return await self._timed("anomalies_for_site", self._anomalies_for_site(site_id, hours))

    async def predict(self, alarm: dict[str, Any]) -> dict[str, Any] | None:
        return await self._timed("predict", self._predict(alarm))

    async def runbooks(self, query: str, fault_type: str | None) -> list[dict[str, Any]]:
        return await self._timed("runbooks", self._runbooks(query, fault_type))

    async def aclose(self) -> None:
        """Release resources (no-op for plain HTTP)."""

    async def _alarms_for_site(self, site_id: str, window_minutes: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def _anomalies_for_site(self, site_id: str, hours: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def _predict(self, alarm: dict[str, Any]) -> dict[str, Any] | None:
        raise NotImplementedError

    async def _runbooks(self, query: str, fault_type: str | None) -> list[dict[str, Any]]:
        raise NotImplementedError


class Upstream(ToolRecorder):
    """W9 path: call gateway / ml-service / rag-service directly over HTTP (TOOLS=http)."""

    def __init__(
        self,
        gateway_url: str | None = None,
        ml_url: str | None = None,
        rag_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.gateway_url = (
            gateway_url or os.getenv("GATEWAY_URL", "http://localhost:8000")
        ).rstrip("/")
        self.ml_url = (ml_url or os.getenv("ML_SERVICE_URL", "http://localhost:8003")).rstrip("/")
        self.rag_url = (rag_url or os.getenv("RAG_SERVICE_URL", "http://localhost:8004")).rstrip(
            "/"
        )
        super().__init__()
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def _alarms_for_site(self, site_id: str, window_minutes: int) -> list[dict[str, Any]]:
        try:
            async with self._client() as c:
                resp = await c.get(f"{self.gateway_url}/api/alarms/enriched/recent")
                resp.raise_for_status()
                alarms = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            self.warnings.append(f"alarms unavailable: {type(exc).__name__}")
            return []
        if not isinstance(alarms, list):
            self.warnings.append("alarms: unexpected payload")
            return []
        return select_site_alarms(alarms, site_id, window_minutes)

    async def _anomalies_for_site(self, site_id: str, hours: int = 1) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        prefix = f"{site_id}-"
        try:
            async with self._client() as c:
                for kpi in ANOMALY_KPIS:
                    resp = await c.get(
                        f"{self.ml_url}/anomalies", params={"kpi": kpi, "hours": hours, "limit": 50}
                    )
                    resp.raise_for_status()
                    for item in resp.json().get("items", []):
                        if str(item.get("cellId", "")).startswith(prefix):
                            found.append({**item, "kpi": kpi})
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            self.warnings.append(f"anomalies unavailable: {type(exc).__name__}")
        found.sort(key=lambda i: float(i.get("score", 0)), reverse=True)
        return found[:10]

    async def _predict(self, alarm: dict[str, Any]) -> dict[str, Any] | None:
        try:
            async with self._client() as c:
                resp = await c.post(f"{self.ml_url}/predict", json={"alarm": alarm})
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            self.warnings.append(f"fault prediction unavailable: {type(exc).__name__}")
            return None

    async def _runbooks(self, query: str, fault_type: str | None) -> list[dict[str, Any]]:
        body = {"query": query[:500], "top_k": 3, "mode": "hybrid", "faultType": fault_type}
        try:
            async with self._client() as c:
                resp = await c.post(f"{self.rag_url}/search", json=body)
                resp.raise_for_status()
                return list(resp.json().get("results", []))
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            self.warnings.append(f"runbooks unavailable: {type(exc).__name__}")
            return []
