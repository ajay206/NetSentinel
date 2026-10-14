"""Tests for API Gateway."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

# Set DISABLE_KAFKA before importing app
os.environ["DISABLE_KAFKA"] = "1"

from api_gateway.main import app, hub  # noqa: E402


@pytest.fixture(autouse=True)
def clear_hub() -> None:
    """Clear hub state before each test."""
    hub.clients.clear()
    hub.recent.clear()
    yield
    hub.clients.clear()
    hub.recent.clear()


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
