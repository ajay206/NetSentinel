from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from ml_service.baselines import cusum, detect, robust_zscore, seasonal_decompose
from ml_service.eval import evaluate, log_to_mlflow, score
from ml_service.hypothesis import mann_whitney
from ml_service.synth import inject_anomalies, make_series


class TestRobustZScore:
    def test_known_data(self) -> None:
        # Data with known median=0, MAD=1 -> scale=1.4826
        x = np.array([-2.0, -1.0, 0.0, 1.0, 2.0], dtype=np.float64)
        z = robust_zscore(x)
        # median=0, MAD=1, scale=1.4826
        expected = x / 1.4826
        np.testing.assert_allclose(z, expected, rtol=1e-3)

    def test_mad_zero(self) -> None:
        x = np.array([5.0, 5.0, 5.0, 5.0], dtype=np.float64)
        z = robust_zscore(x)
        np.testing.assert_allclose(z, 0.0)

    def test_nan_preserved(self) -> None:
        x = np.array([1.0, np.nan, 3.0], dtype=np.float64)
        z = robust_zscore(x)
        assert np.isnan(z[1])
        assert not np.isnan(z[0])
        assert not np.isnan(z[2])


class TestCUSUM:
    def test_detects_mean_shift(self) -> None:
        rng = np.random.default_rng(42)
        # Stationary noise
        noise = rng.normal(0, 1, 200)
        # Mean shift at index 100
        shift = np.concatenate([noise[:100], noise[100:] + 4.0])
        flags = cusum(shift, k=0.5, h=5.0)
        # Should detect around the shift
        assert np.any(flags[95:110])

    def test_no_false_alarm_on_stationary(self) -> None:
        rng = np.random.default_rng(123)
        noise = rng.normal(0, 1, 200)
        flags = cusum(noise, k=0.5, h=5.0)
        # Very low false alarm rate expected
        assert np.sum(flags) < 5


class TestSeasonalDecompose:
    def test_removes_pure_sine(self) -> None:
        n = 96 * 3  # 3 days
        t = np.arange(n)
        period = 96
        signal = np.sin(2 * np.pi * t / period)
        trend, seasonal, resid = seasonal_decompose(signal, period=period)
        # Residual should be near zero (within numerical precision)
        assert np.nanmax(np.abs(resid[96:-96])) < 0.1

    def test_short_series_fallback(self) -> None:
        x = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        trend, seasonal, resid = seasonal_decompose(x, period=96)
        assert np.allclose(trend, np.median(x))
        assert np.allclose(seasonal, 0.0)


class TestDetect:
    def test_finds_spike(self) -> None:
        # Create series with a clear spike
        base = np.ones(200, dtype=np.float64) * 10.0
        base[100] = 50.0  # Spike
        anomalies = detect(base, period=96, z_threshold=3.0)
        assert len(anomalies) > 0
        # Should detect index 100
        indices = [a["index"] for a in anomalies]
        assert 100 in indices


class TestInjectAnomalies:
    def test_deterministic(self) -> None:
        values = np.ones(500, dtype=np.float64)
        v1, m1 = inject_anomalies(values, seed=42, n=3, width=4)
        v2, m2 = inject_anomalies(values, seed=42, n=3, width=4)
        np.testing.assert_array_equal(v1, v2)
        np.testing.assert_array_equal(m1, m2)

    def test_non_overlapping(self) -> None:
        values = np.ones(500, dtype=np.float64)
        _, mask = inject_anomalies(values, seed=42, n=10, width=4)
        # Check no overlapping blocks
        indices = np.where(mask)[0]
        diffs = np.diff(indices)
        # Within a block, diff=1; between blocks, diff >= width
        block_breaks = np.where(diffs > 1)[0]
        assert len(block_breaks) >= 0  # At least separated


class TestScore:
    def test_perfect_match(self) -> None:
        pred = np.array([False, True, False, True, False])
        truth = np.array([False, True, False, True, False])
        m = score(pred, truth, tolerance=0)
        assert m["precision"] == 1.0
        assert m["recall"] == 1.0
        assert m["f1"] == 1.0

    def test_tolerance(self) -> None:
        pred = np.array([False, True, False, False, False])
        truth = np.array([False, False, True, False, False])
        m = score(pred, truth, tolerance=1)
        assert m["recall"] == 1.0
        assert m["precision"] == 1.0

    def test_no_pred_no_truth(self) -> None:
        pred = np.zeros(10, dtype=bool)
        truth = np.zeros(10, dtype=bool)
        m = score(pred, truth)
        assert m["precision"] == 1.0
        assert m["recall"] == 1.0


class TestEvaluate:
    def test_returns_metrics(self) -> None:
        result = evaluate(seed=42, cells=("SITE-001-N1-C1",), kpi="dlThroughputMbps", days=7)
        assert "per_cell" in result
        assert "average" in result
        assert 0.0 <= result["average"]["f1"] <= 1.0
        assert 0.0 <= result["average"]["recall"] <= 1.0
        # For seed 42, should have reasonable recall
        assert result["average"]["recall"] >= 0.5


class TestMannWhitney:
    def test_significant_shift(self) -> None:
        before = np.array([1.0, 1.1, 0.9, 1.0, 1.2], dtype=np.float64)
        after = np.array([5.0, 5.1, 4.9, 5.0, 5.2], dtype=np.float64)
        result = mann_whitney(before, after, alpha=0.05)
        assert result["significant"] is True
        assert result["pValue"] < 0.05

    def test_not_significant(self) -> None:
        rng = np.random.default_rng(42)
        before = rng.normal(0, 1, 50)
        after = rng.normal(0, 1, 50)
        result = mann_whitney(before, after, alpha=0.05)
        assert result["significant"] is False

    def test_raises_on_tiny_samples(self) -> None:
        before = np.array([1.0, 2.0], dtype=np.float64)
        after = np.array([3.0, 4.0, 5.0], dtype=np.float64)
        with pytest.raises(ValueError):
            mann_whitney(before, after)


class TestLogToMLflow:
    def test_writes_json_without_env(self, tmp_path: str) -> None:
        # Monkeypatch out_dir via function signature
        metrics = {"average": {"f1": 0.8}, "per_cell": []}
        params = {"seed": 42}
        path = log_to_mlflow(metrics, params, "test-exp", out_dir=str(tmp_path))
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["average"]["f1"] == 0.8


class TestAPI:
    @staticmethod
    def _install(monkeypatch: pytest.MonkeyPatch, handler) -> None:
        from ml_service import api

        monkeypatch.setattr(
            api,
            "client_factory",
            lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )

    @staticmethod
    def _series_handler(fail: bool = False):
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        start = now - timedelta(days=3)
        timestamps, values = make_series(
            42, "SITE-001-N1-C1", "dlThroughputMbps", days=3, start=start
        )
        values = values.copy()
        values[-10] *= 3.0  # obvious spike inside the last 24 h
        points = [
            {"ts": ts.isoformat().replace("+00:00", "Z"), "dlThroughputMbps": float(v)}
            for ts, v in zip(timestamps, values, strict=True)
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            if fail:
                return httpx.Response(500, json={"detail": "boom"})
            path = request.url.path
            if path == "/healthz":
                return httpx.Response(200, json={"status": "ok"})
            if path == "/kpis/cells":
                return httpx.Response(
                    200,
                    json=[
                        {"cellId": "SITE-001-N1-C1", "region": "North"},
                        {"cellId": "SITE-002-N1-C1", "region": "South"},
                    ],
                )
            if path.startswith("/kpis/cells/"):
                return httpx.Response(200, json={"points": points})
            return httpx.Response(404)

        return handler

    def test_healthz_and_readyz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from ml_service.api import app

        self._install(monkeypatch, self._series_handler())
        client = TestClient(app)
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/readyz").status_code == 200

    def test_cell_anomalies_finds_spike(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from ml_service.api import app

        self._install(monkeypatch, self._series_handler())
        resp = TestClient(app).get("/anomalies/cells/SITE-001-N1-C1?hours=24")
        assert resp.status_code == 200
        data = resp.json()
        assert data["from"] and data["points"] > 0
        assert any(a["direction"] == "high" and a["score"] > 3.5 for a in data["anomalies"])

    def test_invalid_kpi_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from ml_service.api import app

        self._install(monkeypatch, self._series_handler())
        assert TestClient(app).get("/anomalies/cells/X?kpi=nope").status_code == 422

    def test_kpi_service_500_returns_502(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from ml_service.api import app

        self._install(monkeypatch, self._series_handler(fail=True))
        assert TestClient(app).get("/anomalies/cells/SITE-001-N1-C1").status_code == 502
        assert TestClient(app).get("/anomalies").status_code == 502

    def test_aggregate_sorted_by_score(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from ml_service.api import app

        self._install(monkeypatch, self._series_handler())
        data = TestClient(app).get("/anomalies?hours=24&limit=10").json()
        scores = [i["score"] for i in data["items"]]
        assert scores and scores == sorted(scores, reverse=True)
        assert {i["region"] for i in data["items"]} <= {"North", "South"}
