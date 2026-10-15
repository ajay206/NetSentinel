"""Side-effect calls the agents make through the gateway (service token).

The service token may read, draft tickets and write back approved RCA findings; it can never
approve tickets (ADR-016) — the human decision happens in the graph's approval node.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from copilot_orchestrator.clients.upstream import gateway_headers


class GatewayActions:
    def __init__(
        self, gateway_url: str | None = None, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.gateway_url = (
            gateway_url or os.getenv("GATEWAY_URL", "http://localhost:8000")
        ).rstrip("/")
        self._transport = transport
        self.calls: list[dict[str, Any]] = []

    async def _call(self, name: str, method: str, path: str, **kw: Any) -> dict[str, Any] | None:
        t0 = time.perf_counter()
        ok, body = False, None
        try:
            async with httpx.AsyncClient(timeout=8.0, transport=self._transport) as c:
                headers = {**(gateway_headers() or {}), "X-NS-Via": "copilot"}
                r = await c.request(method, f"{self.gateway_url}{path}", headers=headers, **kw)
            ok = r.status_code < 300
            body = r.json() if ok else None
        except (httpx.HTTPError, ValueError):
            body = None
        self.calls.append(
            {
                "name": name,
                "ok": ok,
                "durationMs": int((time.perf_counter() - t0) * 1000),
                "transport": "http",
            }
        )
        return body

    async def incident(self, incident_id: str) -> dict[str, Any] | None:
        return await self._call("get_incident", "GET", f"/api/incidents/{incident_id}")

    async def impact(self, site_id: str) -> dict[str, Any] | None:
        return await self._call(
            "query_topology", "GET", "/api/graph/impact", params={"siteId": site_id}
        )

    async def open_ticket_draft(self, draft: dict[str, Any]) -> dict[str, Any] | None:
        return await self._call("open_ticket_draft", "POST", "/api/tickets/drafts", json=draft)

    async def record_rca(self, finding: dict[str, Any]) -> dict[str, Any] | None:
        return await self._call("kg_write_back", "POST", "/api/graph/rca", json=finding)
