"""W22 observability: request metrics, trace IDs and Prometheus-backed sparklines.

No extra dependencies. The gateway fronts every backend, so per-upstream latency and
error counts measured here are what the console's Service health sparklines show.

* ``MetricsMiddleware`` (pure ASGI) counts requests and records latency per *service*
  label (derived from the path, never from user input such as IDs: keeps cardinality low).
* Every response carries ``X-Trace-Id``; an incoming W3C ``traceparent`` is reused, else a
  new trace ID is made. The ID is logged with the request, so one incident can be followed
  from the Copilot trace view to the gateway logs and Grafana (``trace_id`` log field).
* ``/metrics`` renders Prometheus text format. Prometheus scrapes it (compose profile ``obs``).
* ``Sparklines`` asks Prometheus (``PROMETHEUS_URL``) for the last 30 minutes of p95 latency
  and error rate per service. Unset or unreachable = empty result (the panel just hides them).
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger("api_gateway.obs")

# Prometheus default-ish buckets in seconds
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# path prefix -> service label (fixed set: no IDs, no user input in labels)
_SERVICE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/api/kpi", "kpi-service"),
    ("/api/ml", "ml-service"),
    ("/api/rag", "rag-service"),
    ("/api/copilot", "copilot-orchestrator"),
    ("/api/incidents", "incident-service"),
    ("/api/alarms/actions", "incident-service"),
    ("/api/alarms/workflow", "incident-service"),
    ("/api/tickets", "ticket-service"),
    ("/api/topology", "topology-service"),
    ("/api/graph", "topology-service"),
    ("/api/security", "api-gateway"),
    ("/api/auth", "api-gateway"),
    ("/api/admin", "api-gateway"),
    ("/api/alarms", "api-gateway"),
)
_TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$")
_SKIP = {"/metrics", "/healthz", "/readyz"}


def service_for(path: str) -> str:
    for prefix, name in _SERVICE_PREFIXES:
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            return name
    return "api-gateway"


def trace_id_from(traceparent: str | None) -> str:
    m = _TRACEPARENT_RE.match((traceparent or "").strip().lower())
    if m and m.group(1) != "0" * 32:
        return m.group(1)
    return secrets.token_hex(16)


class Registry:
    """Tiny thread-safe counter + histogram store rendered as Prometheus text."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests: dict[tuple[str, str], int] = {}  # (service, class) -> count
        self.hist: dict[str, list[float]] = {}  # service -> bucket counts + [sum, count]

    def observe(self, service: str, status: int, seconds: float) -> None:
        klass = f"{status // 100}xx"
        with self._lock:
            key = (service, klass)
            self.requests[key] = self.requests.get(key, 0) + 1
            h = self.hist.setdefault(service, [0.0] * (len(BUCKETS) + 2))
            for i, b in enumerate(BUCKETS):
                if seconds <= b:
                    h[i] += 1
            h[-2] += seconds
            h[-1] += 1

    def render(self) -> str:
        out = [
            "# HELP ns_http_requests_total Requests through the gateway by upstream service.",
            "# TYPE ns_http_requests_total counter",
        ]
        with self._lock:
            for (svc, klass), n in sorted(self.requests.items()):
                out.append(f'ns_http_requests_total{{service="{svc}",code="{klass}"}} {n}')
            out += [
                "# HELP ns_http_request_duration_seconds Request latency by upstream service.",
                "# TYPE ns_http_request_duration_seconds histogram",
            ]
            for svc, h in sorted(self.hist.items()):
                name = "ns_http_request_duration_seconds_bucket"
                for i, b in enumerate(BUCKETS):
                    out.append(f'{name}{{service="{svc}",le="{b}"}} {int(h[i])}')
                out.append(f'{name}{{service="{svc}",le="+Inf"}} {int(h[-1])}')
                out.append(f'ns_http_request_duration_seconds_sum{{service="{svc}"}} {h[-2]:.6f}')
                out.append(
                    f'ns_http_request_duration_seconds_count{{service="{svc}"}} {int(h[-1])}'
                )
        return "\n".join(out) + "\n"


registry = Registry()


class MetricsMiddleware:
    """Pure ASGI: time each HTTP request, tag it with a trace ID, count it."""

    def __init__(self, app: Any, reg: Registry | None = None) -> None:
        self.app = app
        self.reg = reg or registry

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        trace_id = trace_id_from(headers.get("traceparent"))
        scope.setdefault("state", {})["trace_id"] = trace_id
        status = {"code": 500}
        start = time.perf_counter()

        async def _send(message: dict) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [(b"x-trace-id", trace_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            if path not in _SKIP:
                elapsed = time.perf_counter() - start
                svc = service_for(path)
                self.reg.observe(svc, status["code"], elapsed)
                logger.info(
                    "request service=%s status=%s ms=%.1f trace_id=%s",
                    svc,
                    status["code"],
                    elapsed * 1000,
                    trace_id,
                )


def links() -> dict[str, str | None]:
    """Console 'Open Grafana' / 'Open Langfuse' / 'Open MLflow' links (None = not configured)."""
    return {
        "grafana": os.getenv("GRAFANA_PUBLIC_URL") or None,
        "langfuse": os.getenv("LANGFUSE_PUBLIC_URL") or None,
        "mlflow": os.getenv("MLFLOW_PUBLIC_URL") or None,
        "prometheus": os.getenv("PROMETHEUS_PUBLIC_URL") or None,
    }


_P95 = (
    "histogram_quantile(0.95, sum by (service, le) "
    "(rate(ns_http_request_duration_seconds_bucket[5m])))"
)
_ERR = (
    'sum by (service) (rate(ns_http_requests_total{code="5xx"}[5m])) / '
    "clamp_min(sum by (service) (rate(ns_http_requests_total[5m])), 1e-9)"
)


class Sparklines:
    """Fetch p95 latency (ms) and error ratio series from Prometheus, cached for 15 s."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, ttl: float = 15.0):
        self.transport = transport
        self.ttl = ttl
        self._cache: tuple[float, dict[str, Any]] | None = None

    async def _range(self, client: httpx.AsyncClient, base: str, query: str) -> dict[str, list]:
        now = time.time()
        resp = await client.get(
            f"{base}/api/v1/query_range",
            params={"query": query, "start": now - 1800, "end": now, "step": 60},
        )
        resp.raise_for_status()
        out: dict[str, list] = {}
        for series in resp.json().get("data", {}).get("result", []):
            svc = series.get("metric", {}).get("service")
            if not svc:
                continue
            vals = []
            for _, v in series.get("values", []):
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    continue
                vals.append(f if f == f else 0.0)  # NaN -> 0
            out[svc] = vals
        return out

    async def get(self) -> dict[str, Any]:
        base = (os.getenv("PROMETHEUS_URL") or "").rstrip("/")
        if not base:
            return {"enabled": False, "services": {}}
        if self._cache and time.monotonic() - self._cache[0] < self.ttl:
            return self._cache[1]
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=2.0) as client:
                p95 = await self._range(client, base, _P95)
                err = await self._range(client, base, _ERR)
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("prometheus unreachable: %s", exc)
            body = {"enabled": True, "error": "prometheus unreachable", "services": {}}
            self._cache = (time.monotonic(), body)
            return body
        services = {
            svc: {
                "p95Ms": [round(v * 1000, 1) for v in p95.get(svc, [])],
                "errorRate": [round(v, 4) for v in err.get(svc, [])],
            }
            for svc in sorted(set(p95) | set(err))
        }
        body = {"enabled": True, "windowMinutes": 30, "stepSeconds": 60, "services": services}
        self._cache = (time.monotonic(), body)
        return body
