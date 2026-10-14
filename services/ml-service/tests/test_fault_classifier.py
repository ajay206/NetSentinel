"""Tests for the Week 7 fault-type classifier."""

from __future__ import annotations

import json

import numpy as np
import xgboost as xgb
from ml_service.classifier import FaultClassifier
from ml_service.features import FEATURE_NAMES, LEAKY_FIELDS, alarm_features
from ml_service.synth_faults import FAULT_TYPES, make_dataset
from ml_service.train_xgb import time_split, train

# ---------------------------------------------------------------------------
# features.py
# ---------------------------------------------------------------------------


def test_features_length():
    alarm = {"alarmType": "communicationsAlarm", "perceivedSeverity": "critical"}
    vec = alarm_features(alarm)
    assert vec.shape == (len(FEATURE_NAMES),)
    assert vec.dtype == np.float32


def test_features_no_leakage():
    """Changing leaky fields must not change the feature vector."""
    base = {
        "alarmType": "communicationsAlarm",
        "perceivedSeverity": "critical",
        "probableCause": "lossOfSignal",
        "enrichment": {"siteKind": "hub", "nodeTypes": ["gNB", "router"]},
        "dedup": {"count": 3},
        "correlation": {"role": "root"},
        "alarmRaisedTime": "2026-10-14T10:00:00Z",
    }
    base_vec = alarm_features(base)

    for field in LEAKY_FIELDS:
        modified = dict(base)
        modified[field] = "CHANGED-VALUE"
        vec = alarm_features(modified)
        np.testing.assert_array_equal(vec, base_vec)


def test_one_hot_correctness():
    alarm = {
        "alarmType": "equipmentAlarm",
        "perceivedSeverity": "major",
        "probableCause": "powerProblem",
        "enrichment": {"siteKind": "access", "nodeTypes": ["gNB"]},
        "dedup": {"count": 2},
        "correlation": {"role": "symptom"},
        "alarmRaisedTime": "2026-10-14T14:30:00Z",
    }
    vec = alarm_features(alarm)
    idx = {name: i for i, name in enumerate(FEATURE_NAMES)}

    # severity_rank: major = 4
    assert vec[idx["severity_rank"]] == 4.0

    # alarmType one-hot
    assert vec[idx["alarmType_equipmentAlarm"]] == 1.0
    assert vec[idx["alarmType_communicationsAlarm"]] == 0.0
    assert vec[idx["alarmType_other"]] == 0.0

    # probableCause one-hot
    assert vec[idx["probableCause_powerProblem"]] == 1.0
    assert vec[idx["probableCause_lossOfSignal"]] == 0.0

    # siteKind one-hot
    assert vec[idx["siteKind_access"]] == 1.0
    assert vec[idx["siteKind_hub"]] == 0.0

    # n_node_types
    assert vec[idx["n_node_types"]] == 1.0
    # has_router
    assert vec[idx["has_router"]] == 0.0
    # dedup_count
    assert vec[idx["dedup_count"]] == 2.0
    # is_root / is_symptom
    assert vec[idx["is_root"]] == 0.0
    assert vec[idx["is_symptom"]] == 1.0


def test_missing_fields_default():
    alarm = {}
    vec = alarm_features(alarm)
    assert vec.shape == (len(FEATURE_NAMES),)
    idx = {name: i for i, name in enumerate(FEATURE_NAMES)}
    # Missing categoricals fall into the 'other' / 'unknown' buckets; hour defaults to 0
    hot = {"alarmType_other", "probableCause_other", "siteKind_unknown", "hour_of_day_cos"}
    for name, i in idx.items():
        assert vec[i] == (1.0 if name in hot else 0.0), name


# ---------------------------------------------------------------------------
# synth_faults.py
# ---------------------------------------------------------------------------


def test_synth_dataset_deterministic():
    a1, c1, l1, t1 = make_dataset(seed=42, n=500)
    a2, c2, l2, t2 = make_dataset(seed=42, n=500)
    assert l1.tolist() == l2.tolist()
    assert t1.tolist() == t2.tolist()
    assert a1 == a2
    assert c1 == c2


def test_synth_labels_cover_all_classes():
    _, _, labels, _ = make_dataset(seed=42, n=3000)
    unique = set(labels.tolist())
    assert unique == set(range(len(FAULT_TYPES)))


def test_synth_timestamps_sorted():
    _, _, _, ts = make_dataset(seed=42, n=1000)
    assert np.all(np.diff(ts) >= 0)


# ---------------------------------------------------------------------------
# train_xgb.py
# ---------------------------------------------------------------------------


def test_time_split_strict_separation():
    """The leakage test: max train ts < min test ts."""
    _, _, _, ts = make_dataset(seed=42, n=3000)
    train_idx, test_idx = time_split(ts, train_frac=0.7)
    assert len(train_idx) > 0
    assert len(test_idx) > 0
    max_train_ts = ts[train_idx].max()
    min_test_ts = ts[test_idx].min()
    assert max_train_ts < min_test_ts


def test_train_writes_registry_and_metrics(tmp_path):
    metrics = train(seed=42, n=1200, days=60, out_dir=str(tmp_path), register=True)
    assert "macro_f1" in metrics
    assert "accuracy" in metrics
    assert "confusion_matrix" in metrics
    assert metrics["macro_f1"] > 0.5

    registry_path = tmp_path / "registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text())
    assert "fault_classifier" in registry
    assert "latest" in registry["fault_classifier"]
    assert "versions" in registry["fault_classifier"]

    version = registry["fault_classifier"]["latest"]
    version_dir = tmp_path / "fault_classifier" / version
    assert (version_dir / "model.json").exists()
    assert (version_dir / "meta.json").exists()


# ---------------------------------------------------------------------------
# classifier.py
# ---------------------------------------------------------------------------


def _train_and_load(tmp_path):
    train(seed=42, n=1200, days=60, out_dir=str(tmp_path), register=True)
    return FaultClassifier.load(name="fault_classifier", models_dir=str(tmp_path), version="latest")


def test_classifier_predict_valid(tmp_path):
    clf = _train_and_load(tmp_path)
    alarm = {
        "alarmType": "communicationsAlarm",
        "perceivedSeverity": "critical",
        "probableCause": "lossOfSignal",
        "enrichment": {"siteKind": "hub", "nodeTypes": ["gNB", "router"]},
        "dedup": {"count": 3},
        "correlation": {"role": "root"},
        "alarmRaisedTime": "2026-10-14T10:00:00Z",
    }
    result = clf.predict(alarm)
    assert result["faultType"] in FAULT_TYPES
    assert 0.0 <= result["confidence"] <= 1.0
    probs = result["probabilities"]
    assert len(probs) == len(FAULT_TYPES)
    assert abs(sum(probs.values()) - 1.0) < 0.01
    assert result["modelVersion"].startswith("v")


def test_classifier_explain_topk_sorted(tmp_path):
    clf = _train_and_load(tmp_path)
    alarm = {
        "alarmType": "equipmentAlarm",
        "perceivedSeverity": "major",
        "probableCause": "powerProblem",
        "enrichment": {"siteKind": "access", "nodeTypes": ["gNB"]},
        "dedup": {"count": 2},
        "correlation": {"role": "symptom"},
        "alarmRaisedTime": "2026-10-14T14:30:00Z",
    }
    result = clf.explain(alarm, top_k=5)
    assert result["faultType"] in FAULT_TYPES
    assert "baseValue" in result
    assert "contributions" in result
    assert len(result["contributions"]) <= 5
    # Sorted by |shap| descending
    shaps = [abs(c["shap"]) for c in result["contributions"]]
    assert shaps == sorted(shaps, reverse=True)


def test_classifier_explain_shap_sum(tmp_path):
    """Sum of all contributions + base ≈ margin for the predicted class."""
    clf = _train_and_load(tmp_path)
    alarm = {
        "alarmType": "qualityOfServiceAlarm",
        "perceivedSeverity": "minor",
        "probableCause": "thresholdCrossed",
        "enrichment": {"siteKind": "core", "nodeTypes": ["router", "server"]},
        "dedup": {"count": 5},
        "correlation": {"role": "root"},
        "alarmRaisedTime": "2026-10-14T22:00:00Z",
    }
    context = {"groupSize": 8, "kpiDropPct": 30.0, "anomalyScore": 5.0}

    result = clf.explain(alarm, context=context, top_k=100)
    pred_class = FAULT_TYPES.index(result["faultType"])

    # Recompute full contributions (all features, not just top_k).
    vec = alarm_features(alarm, context).reshape(1, -1)
    dmatrix = xgb.DMatrix(vec, feature_names=list(clf._feature_names))
    contribs = clf._booster.predict(dmatrix, pred_contribs=True)
    contribs = np.asarray(contribs)

    n_features = len(clf._feature_names)
    expected_cols = (n_features + 1) * len(FAULT_TYPES)
    if contribs.ndim == 2 and contribs.shape[1] == expected_cols:
        contribs = contribs.reshape(1, len(FAULT_TYPES), n_features + 1)

    if contribs.ndim == 3:
        class_contribs = contribs[0, pred_class, :]
    else:
        class_contribs = contribs[0, :]

    base_value = float(class_contribs[-1])
    feature_shaps = class_contribs[:-1]
    total = base_value + float(feature_shaps.sum())

    # Compare against margin output.
    margin = clf._booster.predict(dmatrix, output_margin=True)
    margin = np.asarray(margin).reshape(-1)
    if margin.ndim == 2:
        margin_val = float(margin[0, pred_class])
    else:
        margin_val = float(margin[pred_class])

    assert abs(total - margin_val) < 1e-3


# ---------------------------------------------------------------------------
# api.py (W7 endpoints)
# ---------------------------------------------------------------------------


def test_api_predict_and_explain_auto_trains(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from ml_service import api

    monkeypatch.setattr(api, "MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(api, "_model", None)
    client = TestClient(api.app)
    alarm = {
        "alarmType": "communicationsAlarm",
        "perceivedSeverity": "critical",
        "probableCause": "lossOfSignal",
        "alarmRaisedTime": "2026-10-14T10:00:00Z",
        "enrichment": {"siteKind": "hub", "nodeTypes": ["gNB", "router"]},
        "correlation": {"role": "root"},
    }
    body = {"alarm": alarm, "context": {"groupSize": 9, "kpiDropPct": 70}}
    pred = client.post("/predict", json=body).json()
    assert pred["faultType"] in FAULT_TYPES
    assert (tmp_path / "registry.json").exists()
    exp = client.post("/explain?top_k=3", json=body).json()
    assert exp["faultType"] == pred["faultType"]
    assert len(exp["contributions"]) == 3
    assert client.post("/predict", json={"context": {}}).status_code == 422


def test_api_predict_503_without_model(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from ml_service import api

    monkeypatch.setattr(api, "MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(api, "AUTO_TRAIN", False)
    monkeypatch.setattr(api, "_model", None)
    resp = TestClient(api.app).post("/predict", json={"alarm": {}})
    assert resp.status_code == 503
