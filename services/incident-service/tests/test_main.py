import os

os.environ.setdefault("DISABLE_KAFKA", "1")

from fastapi.testclient import TestClient  # noqa: E402
from incident_service import main  # noqa: E402
from netgen import build_topology  # noqa: E402

LOS = {"perceivedSeverity": "critical", "specificProblem": "LOS", "state": "raised"}


def _alarm(aid: str, site: str, t: str) -> dict:
    return {"id": aid, "siteId": site, "alarmRaisedTime": t, **LOS}


def _client() -> TestClient:
    main.DISABLE_KAFKA = True
    main.clusterer.incidents.clear()
    return TestClient(main.app)


def test_health_and_ready() -> None:
    with _client() as c:
        assert c.get("/healthz").json() == {"status": "ok"}
        assert c.get("/readyz").status_code == 200


def test_ready_503_when_kafka_down(monkeypatch) -> None:
    monkeypatch.setattr(main, "DISABLE_KAFKA", False)
    monkeypatch.setitem(main.state, "connected", False)
    c = TestClient(main.app)  # no lifespan: consumer never starts
    assert c.get("/readyz").status_code == 503


def test_incidents_flow() -> None:
    site = build_topology(seed=42, small=True).sites[-1].site_id
    with _client() as c:
        assert main.handle(_alarm("a1", site, "2026-01-01T00:00:00Z")) is not None
        assert main.handle(_alarm("a2", site, "2026-01-01T00:01:00Z")) is not None
        assert main.handle("not-a-dict") is None
        body = c.get("/incidents").json()
        assert body["total"] == 1
        assert body["stats"]["compressionRatio"] == 2.0
        inc_id = body["items"][0]["id"]
        assert c.get(f"/incidents/{inc_id}").json()["alarmCount"] == 2
        assert c.get("/incidents/INC-0000000000").status_code == 404
        assert c.get("/incidents?status=cleared").json()["total"] == 0
        assert c.get("/stats").json()["incidents"] == 1


def test_prune_bounds_memory() -> None:
    sites = [s.site_id for s in build_topology(seed=42, small=True).sites]
    _client()
    for i in range(5):
        main.handle(_alarm(f"p{i}", sites[i % len(sites)], f"2026-01-0{i + 1}T00:00:00Z"))
    main.prune(max_keep=4)
    assert len(main.clusterer.incidents) == 3  # down to 90% of 4
    assert "p0" not in main.clusterer._alarm_incident
