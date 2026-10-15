"""Step 21: PQC status for the console panel (GET /api/security/pqc, viewer).

* TLS: for each ``PQC_TLS_TARGETS`` entry (``name=host:port``) probe whether a hybrid-only
  (X25519MLKEM768) and a classical-only (X25519) client can complete a handshake. Probing is a
  real handshake in a child process (OpenSSL group policy is per process), cached briefly.
* Model: ml-service ``GET /model/signature`` (ML-DSA-65 verify result on load).
Services without TLS are listed as plaintext so the panel never over-claims.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from ns_pqc import probe_tls

REPORT = "docs/pqc_report.md"
CACHE_S = float(os.getenv("PQC_CACHE_S", "30"))
PLAINTEXT = [
    "api-gateway",
    "kpi-service",
    "ml-service",
    "rag-service",
    "copilot-orchestrator",
    "mcp-server",
    "incident-service",
    "topology-service",
    "ticket-service",
]


def targets() -> list[tuple[str, str, int]]:
    out = []
    for item in filter(None, (s.strip() for s in os.getenv("PQC_TLS_TARGETS", "").split(","))):
        name, _, hostport = item.partition("=")
        host, _, port = hostport.rpartition(":")
        out.append((name, host, int(port)))
    return out


class PqcStatus:
    def __init__(
        self,
        ml_url: Callable[[], str],
        probe: Callable[..., dict[str, Any]] = probe_tls,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.ml_url, self.probe, self.transport = ml_url, probe, transport
        self._cache: tuple[float, dict[str, Any]] | None = None

    async def model(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self.transport) as c:
                r = await c.get(f"{self.ml_url()}/model/signature")
            if r.status_code != 200:
                return {"status": "unknown", "reason": f"ml-service {r.status_code}"}
            return r.json()
        except httpx.HTTPError as exc:
            return {"status": "unknown", "reason": f"ml-service unreachable: {type(exc).__name__}"}

    async def get(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < CACHE_S:
            return self._cache[1]
        cafile = os.getenv("PQC_CA_FILE") or None
        tls_targets = targets()
        probes = await asyncio.gather(
            *(asyncio.to_thread(self.probe, h, p, cafile) for _, h, p in tls_targets)
        )
        tls = [
            {"service": n, "tls": True, **r}
            for (n, _, _), r in zip(tls_targets, probes, strict=True)
        ]
        seen = {t["service"] for t in tls}
        tls += [
            {"service": s, "tls": False, "hybrid": False, "group": None, "hybridOnly": False}
            for s in PLAINTEXT
            if s not in seen
        ]
        body = {
            "checkedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            "tls": tls,
            "model": await self.model(),
            "report": REPORT,
        }
        self._cache = (now, body)
        return body
