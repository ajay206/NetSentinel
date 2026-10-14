"""Tests for API Gateway."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

# Set DISABLE_KAFKA before importing app
os.environ["DISABLE_KAFKA"] = "1"

from api_gateway.main import app, enriched_hub, hub, kpi_activity  # noqa: E402


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
        assert len(data["services"]) == 3
        assert all(s["status"] == "up" for s in data["services"])
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
