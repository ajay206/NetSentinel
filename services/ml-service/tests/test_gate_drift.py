"""W24: eval gate blocks a degraded model; PSI flags drift; /model/info reports the gate."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from ml_service import api, train_xgb
from ml_service.drift import psi, report
from ml_service.gate import decide, run_gate

CFG = Path(__file__).resolve().parents[3] / "evals" / "gate_thresholds.json"


def _train(out: Path, degrade: bool = False) -> Path:
    if degrade:
        orig = train_xgb.make_dataset

        def bad(*a, **k):
            alarms, ctx, labels, ts = orig(*a, **k)
            return alarms, ctx, np.random.default_rng(0).permutation(labels), ts

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(train_xgb, "make_dataset", bad)
            train_xgb.train(n=1500, days=20, out_dir=str(out), register=True)
    else:
        train_xgb.train(n=1500, days=20, out_dir=str(out), register=True)
    return next((out / "fault_classifier").iterdir())


@pytest.fixture(scope="module")
def good(tmp_path_factory):
    return _train(tmp_path_factory.mktemp("good"))


def test_good_model_passes_gate(good):
    r = run_gate(good, CFG, n=800)
    assert r["passed"], r["reasons"]
    assert json.loads((good.parent / f"{good.name}.gate.json").read_text())["passed"] is True
    assert not (good / "gate.json").exists()  # signed file set untouched


def test_degraded_model_is_blocked(tmp_path):
    r = run_gate(_train(tmp_path, degrade=True), CFG, n=800)
    assert not r["passed"]
    assert any("macro_f1" in x for x in r["reasons"])


def test_regression_vs_champion_blocks_even_above_floor():
    cfg = json.loads(CFG.read_text())
    m = {
        "accuracy": 0.82,
        "macro_f1": cfg["champion"]["macro_f1"] - 0.05,
        "per_class_f1": {"fibre_cut": 0.9},
    }
    m["macro_f1"] = max(m["macro_f1"], 0.81)
    out = decide(m, cfg)
    assert not out["passed"] and "regressed" in out["reasons"][0]


def test_psi_stable_vs_shifted():
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=4000), rng.normal(size=4000)
    assert psi(a, b) < 0.05
    assert psi(a, b + 1.0) > 0.2
    assert psi(np.zeros(100), np.zeros(100)) < 0.01
    r = report(np.c_[a, a], np.c_[b, b + 1.0])
    assert r["status"] == "drift" and len(r["drifted"]) == 1


def test_model_info_reports_version_and_gate(good, monkeypatch):
    monkeypatch.setattr(api, "MODELS_DIR", str(good.parent.parent))
    body = TestClient(api.app).get("/model/info").json()
    assert body["version"] == good.name
    assert body["metrics"]["macro_f1"] > 0
    assert body["gate"]["passed"] is True  # written by test_good_model_passes_gate


def test_model_info_without_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "MODELS_DIR", str(tmp_path))
    body = TestClient(api.app).get("/model/info").json()
    assert body["version"] is None and body["loaded"] is False
