"""Tests for API Gateway."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

# Set DISABLE_KAFKA before importing app
os.environ["DISABLE_KAFKA"] = "1"
os.environ["AUTH_DISABLED"] = "1"  # W11 auth is covered in test_auth.py

import api_gateway.main as main  # noqa: E402
from api_gateway import auth as gw_auth  # noqa: E402
from api_gateway.main import app, enriched_hub, hub, kpi_activity  # noqa: E402


@pytest.fixture(autouse=True)
def no_phase1_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 1 /healthz probes never touch real ports in tests."""

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(main, "health_transport", httpx.MockTransport(refuse))
    # W11 auth has its own tests (test_auth.py); these cover the routes themselves
    monkeypatch.setattr(gw_auth.settings, "disabled", True)


@pytest.fixture(autouse=True)
def clear_hub() -> None:
    """Clear hub state before each test."""
    hub.clients.clear()
    hub.recent.clear()
    yield
    hub.clients.clear()
    hub.recent.clear()


@pytest.fixture(autouse=True)
def clear_kpi_activity() -> None:
    """Clear KPI activity state before each test."""
    kpi_activity.total_samples = 0
    kpi_activity._arrival_times.clear()
    kpi_activity._last_sample = None
    kpi_activity._last_timestamp = None
    kpi_activity._kpi_values.clear()
    kpi_activity._cell_ids.clear()
    yield
    kpi_activity.total_samples = 0
    kpi_activity._arrival_times.clear()
    kpi_activity._last_sample = None
    kpi_activity._last_timestamp = None
    kpi_activity._kpi_values.clear()
    kpi_activity._cell_ids.clear()


def test_health_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health returns ok when all dependencies up."""
    monkeypatch.setattr("api_gateway.main.tcp_check", AsyncMock(return_value=True))

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        core = [s for s in data["services"] if s["tier"] == "core"]
        assert len(core) == 3
        assert all(s["status"] == "up" for s in core)
        # W11: Phase 1 services are listed too (down here: nothing is listening)
        names = {s["name"] for s in data["services"]}
        assert {"alarm-ingest", "kpi-service", "ml-service", "rag-service"} <= names
        assert "checkedAt" in data


def test_health_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Health returns degraded when Kafka down."""

    async def mock_tcp_check(host: str, port: int, timeout: float = 1.5) -> bool:
        if port == 9092:
            return False
        return True

    monkeypatch.setattr("api_gateway.main.tcp_check", mock_tcp_check)

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        kafka_svc = next(s for s in data["services"] if s["name"] == "kafka")
        assert kafka_svc["status"] == "down"


def test_recent_alarms_empty() -> None:
    """Recent alarms returns empty list initially."""
    with TestClient(app) as client:
        response = client.get("/api/alarms/recent")
        assert response.status_code == 200
        assert response.json() == []


def test_websocket_snapshot_and_alarm() -> None:
    """WebSocket sends snapshot then receives published alarms."""
    test_alarm = {
        "id": "test-alarm-1",
        "perceivedSeverity": "critical",
        "siteId": "SITE-001",
        "@type": "Alarm",
    }

    with TestClient(app) as client:
        with client.websocket_connect("/ws/alarms") as ws:
            # Receive snapshot
            snapshot_msg = ws.receive_json()
            assert snapshot_msg["type"] == "snapshot"
            assert snapshot_msg["alarms"] == []

            # Publish an alarm via hub
            client.portal.call(hub.publish, test_alarm)

            # Receive alarm
            alarm_msg = ws.receive_json()
            assert alarm_msg["type"] == "alarm"
            assert alarm_msg["alarm"]["id"] == "test-alarm-1"
            assert alarm_msg["alarm"]["perceivedSeverity"] == "critical"


def test_websocket_multiple_clients() -> None:
    """Multiple WebSocket clients receive same alarms."""
    test_alarm = {
        "id": "test-alarm-2",
        "perceivedSeverity": "major",
        "siteId": "SITE-002",
        "@type": "Alarm",
    }

    with TestClient(app) as client:
        with client.websocket_connect("/ws/alarms") as ws1:
            with client.websocket_connect("/ws/alarms") as ws2:
                # Both get snapshot
                ws1.receive_json()
                ws2.receive_json()

                # Publish alarm
                client.portal.call(hub.publish, test_alarm)

                # Both receive alarm
                msg1 = ws1.receive_json()
                msg2 = ws2.receive_json()
                assert msg1["alarm"]["id"] == "test-alarm-2"
                assert msg2["alarm"]["id"] == "test-alarm-2"


def test_recent_alarms_after_publish() -> None:
    """Recent alarms endpoint returns published alarms."""
    test_alarm = {
        "id": "test-alarm-3",
        "perceivedSeverity": "minor",
        "siteId": "SITE-003",
        "@type": "Alarm",
    }

    with TestClient(app) as client:
        client.portal.call(hub.publish, test_alarm)
        response = client.get("/api/alarms/recent")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test-alarm-3"


def test_topology_endpoint() -> None:
    """Topology endpoint returns expected structure with sites having lat/lon."""
    with TestClient(app) as client:
        response = client.get("/api/topology")
        assert response.status_code == 200
        data = response.json()
        # Basic structure checks
        assert "sites" in data
        assert "counts" in data
        assert "cells" in data["counts"]
        assert data["counts"]["cells"] > 0
        # At least one site
        assert len(data["sites"]) > 0
        # Each site has lat and lon
        for site in data["sites"]:
            assert "lat" in site
            assert "lon" in site
            assert isinstance(site["lat"], (int, float))
            assert isinstance(site["lon"], (int, float))


def test_kpi_activity_snapshot_after_records() -> None:
    """KpiActivity snapshot reflects recorded samples."""
    # Record three samples
    sample1 = {
        "cellId": "CELL-1",
        "timestamp": "2024-01-01T00:00:00Z",
        "kpis": {"rsrp": -85.0},
    }
    sample2 = {
        "cellId": "CELL-2",
        "timestamp": "2024-01-01T00:00:01Z",
        "kpis": {"rsrp": -90.0},
    }
    sample3 = {
        "cellId": "CELL-1",
        "timestamp": "2024-01-01T00:00:02Z",
        "kpis": {"sinr": 15.0},
    }

    kpi_activity.record(sample1)
    kpi_activity.record(sample2)
    kpi_activity.record(sample3)

    snap = kpi_activity.snapshot()
    assert snap["totalSamples"] == 3
    # Rate per minute: 3 samples in 60s window -> 3.0
    assert snap["ratePerMin"] == 3.0
    # Averages: rsrp has two values (-85, -90) -> -87.5; sinr has one value (15) -> 15.0
    assert snap["averages"]["rsrp"] == -87.5
    assert snap["averages"]["sinr"] == 15.0
    # Cells reporting: CELL-1 and CELL-2 -> 2
    assert snap["cellsReporting"] == 2
    # Last sample is sample3
    assert snap["lastSample"] == sample3
    assert snap["lastSampleTime"] == "2024-01-01T00:00:02Z"


def test_kpis_activity_endpoint() -> None:
    """GET /api/kpis/activity returns KPI activity snapshot."""
    # Record a sample first
    kpi_activity.record({"cellId": "CELL-1", "kpis": {"rsrp": -80.0}})

    with TestClient(app) as client:
        response = client.get("/api/kpis/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["totalSamples"] == 1
        assert data["ratePerMin"] == 1.0
        assert "rsrp" in data["averages"]
        assert data["averages"]["rsrp"] == -80.0
        assert data["cellsReporting"] == 1


def test_ws_kpis_first_message_type() -> None:
    """WebSocket /ws/kpis sends kpiActivity type as first message."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/kpis") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "kpiActivity"
            # Should have snapshot fields
            assert "totalSamples" in msg
            assert "ratePerMin" in msg
            assert "lastSampleTime" in msg
            assert "lastSample" in msg
            assert "averages" in msg
            assert "cellsReporting" in msg


def test_enriched_ws_snapshot_and_recent() -> None:
    """Enriched alarms are served on /ws/enriched and /api/alarms/enriched/recent."""
    enriched_hub.recent.clear()
    alarm = {"id": "e-1", "siteId": "S-1", "dedup": {"count": 2}, "enrichment": {"region": "North"}}
    enriched_hub.recent.append(alarm)
    client = TestClient(app)
    assert client.get("/api/alarms/enriched/recent").json() == [alarm]
    with client.websocket_connect("/ws/enriched") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "snapshot", "alarms": [alarm]}
    enriched_hub.recent.clear()


async def test_enriched_hub_message_type() -> None:
    ws = AsyncMock()
    enriched_hub.clients.add(ws)
    try:
        await enriched_hub.publish({"id": "e-2"})
        sent = ws.send_text.call_args.args[0]
        assert '"type": "enriched"' in sent
    finally:
        enriched_hub.clients.discard(ws)
        enriched_hub.recent.clear()


def test_kpi_proxy_forwards_and_handles_errors() -> None:
    import api_gateway.main as gw
    import httpx

    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return httpx.Response(200, json={"cellId": "C1", "points": []})

    gw.kpi_transport = httpx.MockTransport(handler)
    try:
        client = TestClient(app)
        resp = client.get("/api/kpi/cells/C1", params={"agg": "1h"})
        assert resp.status_code == 200
        assert resp.json()["cellId"] == "C1"
        assert seen[0].endswith("/kpis/cells/C1?agg=1h")
        assert client.get("/api/kpi/admin").status_code == 404

        def boom(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        gw.kpi_transport = httpx.MockTransport(boom)
        assert client.get("/api/kpi/cells").status_code == 503
    finally:
        gw.kpi_transport = None


def test_ml_proxy_forwards_and_handles_errors() -> None:
    import api_gateway.main as gw
    import httpx

    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return httpx.Response(200, json={"kpi": "dlThroughputMbps", "hours": 24, "items": []})

    gw.ml_transport = httpx.MockTransport(handler)
    try:
        client = TestClient(app)
        resp = client.get("/api/ml/anomalies", params={"hours": "24"})
        assert resp.status_code == 200
        assert seen[0].endswith("/anomalies?hours=24")
        assert client.get("/api/ml/anomalies/cells/C1").status_code == 200
        assert seen[1].endswith("/anomalies/cells/C1")
        assert client.get("/api/ml/train").status_code == 404

        def boom(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        gw.ml_transport = httpx.MockTransport(boom)
        assert client.get("/api/ml/anomalies").status_code == 503
    finally:
        gw.ml_transport = None


def test_ml_post_proxy_predict_and_errors() -> None:
    import api_gateway.main as gw
    import httpx

    seen: list[tuple[str, bytes]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((str(req.url), req.content))
        return httpx.Response(200, json={"faultType": "fibre_cut", "confidence": 0.9})

    gw.ml_transport = httpx.MockTransport(handler)
    try:
        client = TestClient(app)
        resp = client.post("/api/ml/predict", json={"alarm": {"id": "a"}})
        assert resp.status_code == 200
        assert resp.json()["faultType"] == "fibre_cut"
        assert seen[0][0].endswith("/predict")
        assert b'"alarm"' in seen[0][1]
        assert client.post("/api/ml/explain?top_k=3", json={"alarm": {}}).status_code == 200
        assert seen[1][0].endswith("/explain?top_k=3")
        assert client.post("/api/ml/train", json={}).status_code == 404
        assert client.post("/api/ml/predict", content=b"x" * 70_000).status_code == 413

        def boom(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        gw.ml_transport = httpx.MockTransport(boom)
        assert client.post("/api/ml/predict", json={"alarm": {}}).status_code == 503
    finally:
        gw.ml_transport = None


def test_rag_proxy_forwards_and_validates() -> None:
    import api_gateway.main as gw
    import httpx

    seen: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, str(req.url)))
        return httpx.Response(200, json={"results": [], "id": "RB-FIB-001"})

    gw.rag_transport = httpx.MockTransport(handler)
    try:
        client = TestClient(app)
        assert client.post("/api/rag/search", json={"query": "LOS"}).status_code == 200
        assert seen[0] == ("POST", f"{gw.RAG_SERVICE_URL}/search")
        assert client.get("/api/rag/runbooks/RB-FIB-001").status_code == 200
        assert seen[1][1].endswith("/runbooks/RB-FIB-001")
        assert client.get("/api/rag/runbooks/..%2Fsecret").status_code == 404
        assert client.post("/api/rag/search", content=b"x" * 20_000).status_code == 413
        assert len(seen) == 2

        def boom(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        gw.rag_transport = httpx.MockTransport(boom)
        assert client.post("/api/rag/search", json={"query": "LOS"}).status_code == 503
    finally:
        gw.rag_transport = None


def test_copilot_proxy() -> None:
    import api_gateway.main as gw
    import httpx

    seen: list[bytes] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.content)
        return httpx.Response(200, json={"generatedBy": "fallback"})

    gw.copilot_transport = httpx.MockTransport(handler)
    try:
        client = TestClient(app)
        resp = client.post("/api/copilot/analyze", json={"site_id": "SITE-012"})
        assert resp.status_code == 200 and resp.json()["generatedBy"] == "fallback"
        assert b"SITE-012" in seen[0]
        assert client.post("/api/copilot/analyze", content=b"x" * 5_000).status_code == 413

        def boom(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        gw.copilot_transport = httpx.MockTransport(boom)
        assert client.post("/api/copilot/analyze", json={}).status_code == 503
    finally:
        gw.copilot_transport = None


def test_healthz_and_readyz() -> None:
    """W12: liveness/readiness probes (Kafka is disabled in tests, so readiness skips it)."""
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        resp = client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready", "kafka": "skipped", "topology": "loaded"}


def test_incidents_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """W13: /api/incidents forwards to incident-service; ids are validated first."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"items": [], "total": 0})

    monkeypatch.setattr(main, "incident_transport", httpx.MockTransport(handler))
    with TestClient(app) as client:
        assert client.get("/api/incidents?status=open").json() == {"items": [], "total": 0}
        assert client.get("/api/incidents/INC-0123456789").status_code == 200
        assert client.get("/api/incidents/..%2Fadmin").status_code == 404
    assert seen[0].endswith("/incidents?status=open")
    assert seen[1].endswith("/incidents/INC-0123456789")
    assert len(seen) == 2


def test_incidents_proxy_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(main, "incident_transport", httpx.MockTransport(refuse))
    with TestClient(app) as client:
        assert client.get("/api/incidents").status_code == 503


def test_copilot_analyze_siteid_through_gateway(monkeypatch) -> None:
    """smoke.py, `make analyze` and the console send `siteId`; the real copilot app must
    accept it end-to-end via the gateway proxy (was 422: extra=forbid + no alias)."""
    import api_gateway.main as gw
    import httpx
    from copilot_orchestrator.api import app as copilot_app
    from copilot_orchestrator.api import get_llm, get_upstream
    from copilot_orchestrator.clients.llm import OffLLM
    from copilot_orchestrator.clients.upstream import Upstream

    def upstream_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [], "results": []})

    copilot_app.dependency_overrides[get_llm] = OffLLM
    copilot_app.dependency_overrides[get_upstream] = lambda: Upstream(
        "http://gw", "http://ml", "http://rag", transport=httpx.MockTransport(upstream_handler)
    )
    gw.copilot_transport = httpx.ASGITransport(app=copilot_app)
    try:
        client = TestClient(app)
        for key in ("siteId", "site_id"):
            resp = client.post("/api/copilot/analyze", json={key: "SITE-012", "window": "30m"})
            assert resp.status_code != 422, resp.text
            # valid request: 200/404, or 502 because the stub upstream returns no real alarm payload
            assert resp.status_code in (200, 404, 502)
        bad = client.post("/api/copilot/analyze", json={"site": "SITE-012"})
        assert bad.status_code == 422
    finally:
        gw.copilot_transport = None
        copilot_app.dependency_overrides.clear()


def test_graph_proxy_end_to_end_with_real_topology_service(monkeypatch) -> None:
    """W14: gateway -> topology-service (memory backend) answers the L-12 question."""
    monkeypatch.setenv("GRAPH_BACKEND", "memory")
    from topology_service import main as topo

    with TestClient(topo.app) as tc:

        def forward(req: httpx.Request) -> httpx.Response:
            r = tc.request(
                req.method,
                req.url.path,
                params=req.url.params,
                content=req.content,
                headers={"Content-Type": "application/json"},
            )
            return httpx.Response(r.status_code, content=r.content, headers=r.headers)

        monkeypatch.setattr(main, "topology_transport", httpx.MockTransport(forward))
        with TestClient(app) as client:
            body = client.get("/api/graph/impact?linkId=LNK-012").json()
            assert [s["siteId"] for s in body["impactedSites"]] == ["SITE-010"]
            assert client.get("/api/graph/impact?linkId=LNK-999").status_code == 404
            assert client.get("/api/graph/impact").status_code == 400
            assert len(client.get("/api/graph/queries").json()["items"]) == 20
            assert client.post("/api/graph/queries/BAD-NAME", json={}).status_code == 404


def test_graph_proxy_down_is_503(monkeypatch) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(main, "topology_transport", httpx.MockTransport(refuse))
    with TestClient(app) as client:
        r = client.get("/api/graph/impact?linkId=LNK-012")
        assert r.status_code == 503 and "graph" in r.json()["detail"]
