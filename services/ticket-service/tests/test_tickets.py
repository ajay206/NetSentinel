"""W16: drafts, role checks, the approval state machine and the append-only audit chain."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

OP = {"X-NS-User": "operator", "X-NS-Role": "operator"}
VIEW = {"X-NS-User": "viewer", "X-NS-Role": "viewer"}
SVC = {"X-NS-User": "service", "X-NS-Role": "service", "X-NS-Via": "mcp"}
ADMIN = {"X-NS-User": "admin", "X-NS-Role": "admin"}
DRAFT = {
    "title": "Fibre cut on LNK-012 isolates SITE-010",
    "description": "LOS on SITE-010; splice team needed.",
    "severity": "critical",
    "siteId": "SITE-010",
    "incidentId": "INC-0123456789",
    "faultType": "fibre_cut",
    "runbookIds": ["RB-FIB-001"],
    "sourceIds": ["alm-root-0001", "LNK-012"],
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.delenv("TICKET_SERVICE_TOKEN", raising=False)
    from ticket_service.main import app

    with TestClient(app) as c:
        yield c


def _draft(c, headers=OP, **kw):
    return c.post("/tickets/drafts", json={**DRAFT, **kw}, headers=headers)


def test_operator_drafts_and_approves_with_full_audit(client):
    r = _draft(client)
    assert r.status_code == 201
    t = r.json()
    assert t["status"] == "draft" and t["createdBy"] == "operator" and t["version"] == 1
    a = client.post(f"/tickets/{t['id']}/approve", json={"note": "ok"}, headers=OP)
    assert a.status_code == 200
    assert a.json()["status"] == "approved" and a.json()["decidedBy"] == "operator"
    entries = client.get(f"/tickets/{t['id']}/audit").json()["entries"]
    assert [(e["action"], e["fromStatus"], e["toStatus"]) for e in entries] == [
        ("created", None, "draft"),
        ("approved", "draft", "approved"),
    ]
    assert entries[1]["prevHash"] == entries[0]["hash"]
    assert client.get("/audit/verify").json() == {
        "ok": True,
        "entries": 2,
        "head": entries[1]["hash"],
    }


def test_viewer_cannot_draft_or_decide(client):
    assert _draft(client, VIEW).status_code == 403
    tid = _draft(client).json()["id"]
    assert client.post(f"/tickets/{tid}/approve", json={}, headers=VIEW).status_code == 403
    assert client.get(f"/tickets/{tid}").json()["status"] == "draft"


def test_service_principal_drafts_only(client):
    t = _draft(client, SVC).json()
    assert t["createdVia"] == "mcp" and t["createdBy"] == "service:mcp"
    for d in ("approve", "reject"):
        r = client.post(f"/tickets/{t['id']}/{d}", json={"note": "x"}, headers=SVC)
        assert r.status_code == 403
    assert len(client.get(f"/tickets/{t['id']}/audit").json()["entries"]) == 1


def test_state_machine_reject_needs_note_and_no_second_decision(client):
    tid = _draft(client).json()["id"]
    assert client.post(f"/tickets/{tid}/reject", json={}, headers=OP).status_code == 422
    r = client.post(f"/tickets/{tid}/reject", json={"note": "duplicate"}, headers=ADMIN)
    assert r.json()["status"] == "rejected" and r.json()["decisionNote"] == "duplicate"
    assert client.post(f"/tickets/{tid}/approve", json={}, headers=OP).status_code == 409
    stale = _draft(client).json()["id"]
    assert (
        client.post(f"/tickets/{stale}/approve", json={"version": 7}, headers=OP).status_code == 409
    )


def test_validation_identity_and_listing(client):
    assert _draft(client, runbookIds=["rm -rf"]).status_code == 422
    assert _draft(client, siteId="S-1").status_code == 422
    assert _draft(client, bogus=1).status_code == 422
    assert client.post("/tickets/drafts", json=DRAFT).status_code == 401
    assert client.get("/tickets/TKT-XYZ").status_code == 404
    assert client.post("/tickets/TKT-0000000000/approve", json={}, headers=OP).status_code == 404
    _draft(client)
    _draft(client, incidentId="INC-AAAAAAAAAA")
    body = client.get("/tickets", params={"incidentId": "INC-AAAAAAAAAA"}).json()
    assert len(body["items"]) == 1 and body["counts"]["draft"] == 2
    assert client.get("/readyz").json() == {"status": "ready"}


def test_internal_token_required_when_set(client, monkeypatch):
    monkeypatch.setenv("TICKET_SERVICE_TOKEN", "t0k")
    assert _draft(client).status_code == 401
    assert _draft(client, {**OP, "X-NS-Internal-Token": "t0k"}).status_code == 201


def test_audit_is_append_only_and_tamper_evident(client):
    from ticket_service.main import app

    tid = _draft(client).json()["id"]
    client.post(f"/tickets/{tid}/approve", json={}, headers=OP)
    engine = app.state.store.engine
    for stmt in ("UPDATE ticket_audit SET actor='mallory'", "DELETE FROM ticket_audit"):
        with pytest.raises(sa.exc.DatabaseError), engine.begin() as conn:
            conn.execute(sa.text(stmt))
    # Bypass the trigger (as a DBA could) and the hash chain still catches the edit
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TRIGGER ticket_audit_no_update"))
        conn.execute(sa.text("UPDATE ticket_audit SET actor='mallory' WHERE seq=1"))
    v = client.get("/audit/verify").json()
    assert v["ok"] is False and v["brokenAt"] == 1
