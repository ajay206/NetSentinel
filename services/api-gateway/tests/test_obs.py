"""W22: gateway metrics, trace IDs and Prometheus sparklines."""

from __future__ import annotations

import httpx
from api_gateway import obs
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _app(reg: obs.Registry) -> FastAPI:
    app = FastAPI()

    @app.get("/api/kpi/cells/{cell}")
    def kpi(cell: str) -> dict:
        return {"cell": cell}

    @app.get("/api/ml/boom")
    def boom() -> None:
        raise RuntimeError("x")

    app.add_middleware(obs.MetricsMiddleware, reg=reg)
    return app


def test_service_labels_are_fixed_and_low_cardinality():
    assert obs.service_for("/api/kpi/cells/CELL-1") == "kpi-service"
    assert obs.service_for("/api/incidents/INC-0123456789") == "incident-service"
    assert obs.service_for("/api/alarms/actions") == "incident-service"
    assert obs.service_for("/api/alarms/recent") == "api-gateway"
    assert obs.service_for("/api/kpiX") == "api-gateway"
    assert obs.service_for("/whatever/../x") == "api-gateway"


def test_traceparent_reused_else_new():
    tid = "4bf92f3577b34da6a3ce929d0e0e4736"
    assert obs.trace_id_from(f"00-{tid}-00f067aa0ba902b7-01") == tid
    assert len(obs.trace_id_from("garbage")) == 32
    assert obs.trace_id_from(None) != obs.trace_id_from(None)


def test_middleware_counts_and_tags_responses():
    reg = obs.Registry()
    c = TestClient(_app(reg), raise_server_exceptions=False)
    tid = "4bf92f3577b34da6a3ce929d0e0e4736"
    r = c.get("/api/kpi/cells/CELL-9", headers={"traceparent": f"00-{tid}-00f067aa0ba902b7-01"})
    assert r.headers["x-trace-id"] == tid
    assert c.get("/api/ml/boom").status_code == 500
    text = reg.render()
    assert 'ns_http_requests_total{service="kpi-service",code="2xx"} 1' in text
    assert 'ns_http_requests_total{service="ml-service",code="5xx"} 1' in text
    assert 'ns_http_request_duration_seconds_count{service="kpi-service"} 1' in text
    assert "CELL-9" not in text


async def test_sparklines_disabled_without_prometheus(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)
    assert await obs.Sparklines().get() == {"enabled": False, "services": {}}


async def test_sparklines_from_prometheus(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_URL", "http://prom:9090")

    def handler(req: httpx.Request) -> httpx.Response:
        q = req.url.params["query"]
        val = "0.12" if "histogram_quantile" in q else "NaN"
        return httpx.Response(
            200,
            json={
                "data": {
                    "result": [
                        {"metric": {"service": "ml-service"}, "values": [[1, val], [2, val]]}
                    ]
                }
            },
        )

    body = await obs.Sparklines(httpx.MockTransport(handler)).get()
    assert body["services"]["ml-service"] == {"p95Ms": [120.0, 120.0], "errorRate": [0.0, 0.0]}


async def test_sparklines_survive_prometheus_outage(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_URL", "http://prom:9090")
    t = httpx.MockTransport(lambda r: httpx.Response(503))
    body = await obs.Sparklines(t).get()
    assert body["enabled"] and body["services"] == {} and "error" in body


def test_links_from_env(monkeypatch):
    monkeypatch.setenv("GRAFANA_PUBLIC_URL", "http://localhost:3000")
    monkeypatch.delenv("LANGFUSE_PUBLIC_URL", raising=False)
    assert obs.links()["grafana"] == "http://localhost:3000"
    assert obs.links()["langfuse"] is None
