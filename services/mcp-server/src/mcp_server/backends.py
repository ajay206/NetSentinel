from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, NoReturn

import httpx

TRANSPORT: httpx.AsyncBaseTransport | None = None


def gateway_headers() -> dict[str, str] | None:
    """W11: the gateway requires auth; internal callers send GATEWAY_SERVICE_TOKEN."""
    token = os.getenv("GATEWAY_SERVICE_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else None


class BackendError(Exception):
    """Raised when a backend service call fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Backends:
    """HTTP clients for Phase 1 backend services."""

    def __init__(self) -> None:
        self.gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
        self.ml_service_url = os.getenv("ML_SERVICE_URL", "http://localhost:8003")
        self.rag_service_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8004")
        self._timeout = httpx.Timeout(5.0)
        self._transport = TRANSPORT

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        )

    @staticmethod
    def _raise_backend_error(service: str, exc: Exception) -> NoReturn:
        if isinstance(exc, ValueError):
            msg = f"{service} error: non-JSON response"
        elif isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            msg = f"{service} error: HTTP {status}"
        elif isinstance(exc, httpx.ConnectError):
            msg = f"{service} error: connection failed"
        elif isinstance(exc, httpx.TimeoutException):
            msg = f"{service} error: timeout"
        else:
            msg = f"{service} error: {exc.__class__.__name__}"
        raise BackendError(msg) from exc

    async def alarms_for_site(self, site_id: str, window_minutes: int) -> list[dict[str, Any]]:
        """Fetch enriched alarms and filter to site within time window."""
        url = f"{self.gateway_url}/api/alarms/enriched/recent"
        async with self._client() as client:
            try:
                resp = await client.get(url, headers=gateway_headers())
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                self._raise_backend_error("gateway", exc)

        if not isinstance(data, list):
            raise BackendError("gateway error: expected list response")

        matching: list[dict[str, Any]] = []
        for alarm in data:
            if not isinstance(alarm, dict):
                continue
            if alarm.get("siteId") == site_id:
                matching.append(alarm)
                continue
            correlation = alarm.get("correlation")
            if isinstance(correlation, dict) and correlation.get("rootSiteId") == site_id:
                matching.append(alarm)
                continue
            enrichment = alarm.get("enrichment")
            if isinstance(enrichment, dict) and enrichment.get("parentSiteId") == site_id:
                matching.append(alarm)
                continue

        if not matching:
            return []

        def parse_time(ts: str | None) -> datetime | None:
            if not ts:
                return None
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return None

        parsed = [(a, parse_time(a.get("alarmRaisedTime"))) for a in matching]
        valid = [(a, t) for a, t in parsed if t is not None]
        if not valid:
            return []

        newest = max(t for _, t in valid)
        cutoff = newest - timedelta(minutes=window_minutes)
        filtered = [a for a, t in valid if t >= cutoff]

        severity_rank = {
            "critical": 0,
            "major": 1,
            "minor": 2,
            "warning": 3,
            "indeterminate": 4,
        }

        def sort_key(alarm: dict[str, Any]) -> tuple[int, int, datetime]:
            correlation = alarm.get("correlation")
            role = correlation.get("role") if isinstance(correlation, dict) else None
            role_rank = 0 if role == "root" else 1
            sev = str(alarm.get("perceivedSeverity", "")).lower()
            sev_rank = severity_rank.get(sev, 9)
            raised = parse_time(alarm.get("alarmRaisedTime")) or datetime.min
            return (role_rank, sev_rank, raised)

        filtered.sort(key=sort_key)
        return filtered[:20]

    async def anomalies_for_site(self, site_id: str, hours: int = 1) -> list[dict[str, Any]]:
        """Fetch KPI anomalies for cells belonging to the site."""
        kpis = ("dlThroughputMbps", "availabilityPct", "rrcSetupSuccessPct")
        all_anomalies: list[dict[str, Any]] = []
        prefix = f"{site_id}-"

        async with self._client() as client:
            for kpi in kpis:
                url = f"{self.ml_service_url}/anomalies"
                params = {"kpi": kpi, "hours": hours, "limit": 50}
                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except (httpx.HTTPError, ValueError) as exc:
                    self._raise_backend_error("ml", exc)

                items = data.get("items", []) if isinstance(data, dict) else []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    cell_id = item.get("cellId")
                    if isinstance(cell_id, str) and cell_id.startswith(prefix):
                        item_with_kpi = dict(item)
                        item_with_kpi["kpi"] = kpi
                        all_anomalies.append(item_with_kpi)

        all_anomalies.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_anomalies[:10]

    async def predict_fault(self, alarm: dict[str, Any]) -> dict[str, Any]:
        """Predict fault type from alarm."""
        url = f"{self.ml_service_url}/predict"
        payload = {"alarm": alarm}
        async with self._client() as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                self._raise_backend_error("ml", exc)

    async def search_runbooks(
        self, query: str, fault_type: str | None, top_k: int, mode: str = "hybrid"
    ) -> list[dict[str, Any]]:
        """Search runbooks via RAG service."""
        url = f"{self.rag_service_url}/search"
        payload: dict[str, Any] = {
            "query": query[:500],
            "top_k": top_k,
            "mode": mode,
        }
        if fault_type:
            payload["faultType"] = fault_type
        async with self._client() as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                self._raise_backend_error("rag", exc)

        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            raise BackendError("rag error: unexpected search payload")
        return results

    async def get_runbook(self, runbook_id: str) -> dict[str, Any]:
        """Fetch a single runbook by ID."""
        url = f"{self.rag_service_url}/runbooks/{runbook_id}"
        async with self._client() as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                self._raise_backend_error("rag", exc)

    async def query_topology(
        self, target: dict[str, str] | None, query: str | None, params: dict[str, Any]
    ) -> dict[str, Any]:
        """W14: impact analysis or a named catalogue query, via the gateway (graph profile)."""
        async with self._client() as client:
            try:
                if target is not None:
                    resp = await client.get(
                        f"{self.gateway_url}/api/graph/impact",
                        params=target,
                        headers=gateway_headers(),
                    )
                else:
                    resp = await client.post(
                        f"{self.gateway_url}/api/graph/queries/{query}",
                        json=params,
                        headers=gateway_headers(),
                    )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                self._raise_backend_error("topology", exc)

    async def open_ticket_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        """W16: create a ticket DRAFT via the gateway (the service token can draft, not approve)."""
        headers = {**(gateway_headers() or {}), "X-NS-Via": "mcp"}
        async with self._client() as client:
            try:
                resp = await client.post(
                    f"{self.gateway_url}/api/tickets/drafts", json=draft, headers=headers
                )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                self._raise_backend_error("ticket", exc)
