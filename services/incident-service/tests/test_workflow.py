"""Step 13b: operator workflow (ack / assign / resolve / notes) on incidents and alarms."""

import itertools
import os

os.environ.setdefault("DISABLE_KAFKA", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from incident_service import main  # noqa: E402
from incident_service.workflow import ActionError, apply, new_workflow  # noqa: E402
from netgen import build_topology  # noqa: E402

_ids = itertools.count()
OP = {"X-NS-User": "operator", "X-NS-Role": "operator"}


@pytest.fixture
def setup():
    main.DISABLE_KAFKA = True
    main.clusterer.incidents.clear()
    main.workflow.incidents.clear()
    main.workflow.alarms.clear()
    site = build_topology(seed=42, small=True).sites[-1].site_id
    inc = main.handle(
        {
            "id": f"wf-{next(_ids)}",
            "siteId": site,
            "alarmRaisedTime": "2026-01-01T00:00:00Z",
            "perceivedSeverity": "critical",
            "specificProblem": "LOS",
            "state": "raised",
        }
    )
    return TestClient(main.app), inc["id"]


def test_incident_ack_assign_resolve(setup):
    c, inc = setup
    assert c.get(f"/incidents/{inc}").json()["workflow"] is None
    r = c.post(f"/incidents/{inc}/actions", json={"action": "ack"}, headers=OP)
    assert r.json()["workflow"]["state"] == "acknowledged"
    r = c.post(
        f"/incidents/{inc}/actions", json={"action": "assign", "assignee": "noc.bob"}, headers=OP
    )
    assert r.json()["workflow"]["assignee"] == "noc.bob"
    assert (
        c.post(f"/incidents/{inc}/actions", json={"action": "resolve"}, headers=OP).status_code
        == 400
    )
    r = c.post(
        f"/incidents/{inc}/actions", json={"action": "resolve", "note": "fibre spliced"}, headers=OP
    )
    wf = r.json()["workflow"]
    assert wf["state"] == "resolved" and wf["resolvedBy"] == "operator"
    assert [n["action"] for n in wf["notes"]] == ["ack", "assign", "resolve"]
    assert c.get("/incidents").json()["items"][0]["workflow"]["state"] == "resolved"


@pytest.mark.parametrize(
    "headers,status",
    [
        ({}, 403),
        ({"X-NS-User": "viewer", "X-NS-Role": "viewer"}, 403),
        ({"X-NS-Role": "operator"}, 400),
        ({"X-NS-User": "admin", "X-NS-Role": "admin"}, 200),
    ],
)
def test_role_is_enforced_again(setup, headers, status):
    c, inc = setup
    r = c.post(f"/incidents/{inc}/actions", json={"action": "ack"}, headers=headers)
    assert r.status_code == status


def test_unknown_incident_404(setup):
    c, _ = setup
    r = c.post("/incidents/INC-0000000000/actions", json={"action": "ack"}, headers=OP)
    assert r.status_code == 404


def test_alarm_actions_and_listing(setup):
    c, _ = setup
    key = "SITE-001|equipmentAlarm|lossOfSignal|LOS / fibre"
    r = c.post("/alarms/actions", json={"key": key, "action": "ack", "note": "seen"}, headers=OP)
    assert r.status_code == 200 and r.json()["workflow"]["ackedBy"] == "operator"
    assert c.get("/alarms/workflow").json()["items"][key]["state"] == "acknowledged"
    bad = c.post("/alarms/actions", json={"key": key, "action": "assign"}, headers=OP)
    assert bad.status_code == 422


def test_apply_rules():
    wf = new_workflow()
    apply(wf, "resolve", "op", note="done", now=1.0)
    with pytest.raises(ActionError):
        apply(wf, "ack", "op")
    with pytest.raises(ActionError):
        apply(new_workflow(), "assign", "op", assignee="Bad Name")
    with pytest.raises(ActionError):
        apply(new_workflow(), "note", "op", note="   ")
    many = new_workflow()
    for i in range(60):
        apply(many, "note", "op", note=f"n{i}")
    assert len(many["notes"]) == 50 and many["notes"][-1]["text"] == "n59"


def test_internal_token_required_when_set(setup, monkeypatch):
    c, inc = setup
    monkeypatch.setenv("INCIDENT_SERVICE_TOKEN", "test-token")
    body = {"action": "ack"}
    assert c.post(f"/incidents/{inc}/actions", json=body, headers=OP).status_code == 401
    bad = {**OP, "X-NS-Internal-Token": "wrong"}
    assert c.post(f"/incidents/{inc}/actions", json=body, headers=bad).status_code == 401
    good = {**OP, "X-NS-Internal-Token": "test-token"}
    assert c.post(f"/incidents/{inc}/actions", json=body, headers=good).status_code == 200
