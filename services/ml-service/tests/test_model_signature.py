"""Step 21: ML-DSA verify on model load (MODEL_VERIFY=enforce refuses a tampered model)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ml_service import api
from ml_service.train_xgb import train
from ns_pqc import generate_key

ALARM = {
    "alarmId": "a1",
    "siteId": "SITE-010",
    "severity": "critical",
    "alarmType": "LOS",
    "timestamp": "2026-10-15T08:00:00Z",
    "probableCause": "loss of signal",
}


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    out = tmp_path_factory.mktemp("models")
    train(n=300, days=5, out_dir=str(out), register=True)
    return out


@pytest.fixture
def svc(models, tmp_path, monkeypatch):
    priv, pub = tmp_path / "k.pem", tmp_path / "p.pem"
    generate_key(priv, pub)
    monkeypatch.setattr(api, "MODELS_DIR", str(models))
    monkeypatch.setattr(api, "MODEL_SIGNING_PUBKEY", str(pub))
    monkeypatch.setattr(api, "MODEL_VERIFY", "enforce")
    monkeypatch.setattr(api, "_model", None)
    monkeypatch.setattr(api, "_signature", {"status": "off", "reason": ""})
    sig = api._version_dir() / "signature.json"
    sig.unlink(missing_ok=True)
    api.sign_dir(api._version_dir(), priv)
    yield TestClient(api.app)
    sig.unlink(missing_ok=True)


def test_signed_model_passes_and_serves(svc):
    body = svc.get("/model/signature").json()
    assert body["status"] == "pass" and body["alg"] == "ML-DSA-65" and body["policy"] == "enforce"
    assert svc.post("/predict", json={"alarm": ALARM}).status_code == 200


def test_tampered_model_is_refused_under_enforce(svc):
    model = api._version_dir() / "meta.json"
    original = model.read_text()
    model.write_text(original + " ")
    try:
        r = svc.post("/predict", json={"alarm": ALARM})
        assert r.status_code == 503 and "digest mismatch: meta.json" in r.json()["detail"]
        assert svc.get("/model/signature").json()["status"] == "fail"
    finally:
        model.write_text(original)


def test_warn_policy_serves_unsigned_but_reports_it(svc, monkeypatch):
    (api._version_dir() / "signature.json").unlink()
    monkeypatch.setattr(api, "MODEL_VERIFY", "warn")
    assert svc.post("/predict", json={"alarm": ALARM}).status_code == 200
    assert svc.get("/model/signature").json()["status"] == "unsigned"


def test_auto_train_signs_with_release_key(tmp_path, monkeypatch):
    priv, pub = tmp_path / "k.pem", tmp_path / "p.pem"
    generate_key(priv, pub)
    for k, v in {
        "MODELS_DIR": str(tmp_path / "m"),
        "MODEL_SIGNING_KEY": str(priv),
        "MODEL_SIGNING_PUBKEY": str(pub),
        "MODEL_VERIFY": "enforce",
        "AUTO_TRAIN": True,
        "_model": None,
    }.items():
        monkeypatch.setattr(api, k, v)
    monkeypatch.setattr("ml_service.train_xgb.train", lambda **kw: train(n=300, days=5, **kw))
    assert TestClient(api.app).get("/model/signature").json()["status"] == "pass"
