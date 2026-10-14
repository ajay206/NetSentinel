from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ml_service.baselines import detect
from ml_service.classifier import FaultClassifier
from ml_service.synth import KPI_NAMES

app = FastAPI(title="ML Service - anomalies and fault classifier", version="0.2.0")

KPI_SERVICE_URL = os.environ.get("KPI_SERVICE_URL", "http://localhost:8002")
ANOMALY_Z = float(os.environ.get("ANOMALY_Z", "3.5"))
MODELS_DIR = os.environ.get("MODELS_DIR", "models")
MODEL_NAME = os.environ.get("MODEL_NAME", "fault_classifier")
AUTO_TRAIN = os.environ.get("AUTO_TRAIN", "1") == "1"
logger = logging.getLogger("ml-service")
PORT = int(os.environ.get("PORT", "8003"))

BASELINE_HOURS = 168  # always learn the baseline from up to 7 days of history


def _default_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10.0)


# Factory for test injection
client_factory: Callable[[], httpx.AsyncClient] = _default_client


def _scan(
    timestamps: list[datetime], values: np.ndarray, since: datetime
) -> list[dict[str, object]]:
    """Run detection on the full history, keep anomalies at or after `since`."""
    out: list[dict[str, object]] = []
    for a in detect(values, z_threshold=ANOMALY_Z):
        idx = int(a["index"])
        if idx >= len(timestamps) or timestamps[idx] < since or np.isnan(values[idx]):
            continue
        out.append(
            {
                "ts": timestamps[idx].isoformat().replace("+00:00", "Z"),
                "value": round(float(values[idx]), 3),
                "score": a["score"],
                "method": a["method"],
                "direction": a["direction"],
            }
        )
    return out


class AnomalyPoint(BaseModel):
    ts: str
    value: float
    score: float
    method: str
    direction: str


class CellAnomaliesResponse(BaseModel):
    cellId: str
    kpi: str
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    threshold: float
    points: int
    anomalies: list[AnomalyPoint]


class AggregateAnomalyItem(BaseModel):
    cellId: str
    region: str
    ts: str
    value: float
    score: float
    method: str
    direction: str


class AggregateAnomaliesResponse(BaseModel):
    kpi: str
    hours: int
    items: list[AggregateAnomalyItem]


class HealthResponse(BaseModel):
    status: str


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse:
    async with client_factory() as client:
        try:
            resp = await client.get(f"{KPI_SERVICE_URL}/healthz")
            if resp.status_code == 200:
                return HealthResponse(status="ok")
        except Exception:
            pass
    raise HTTPException(status_code=503, detail="kpi-service unavailable")


async def _fetch_series(
    client: httpx.AsyncClient,
    cell_id: str,
    kpi: str,
    from_ts: datetime,
    to_ts: datetime,
) -> tuple[list[datetime], np.ndarray]:
    """Fetch 15m aggregated series from kpi-service."""
    params = {
        "agg": "15m",
        "from": from_ts.isoformat().replace("+00:00", "Z"),
        "to": to_ts.isoformat().replace("+00:00", "Z"),
    }
    resp = await client.get(f"{KPI_SERVICE_URL}/kpis/cells/{cell_id}", params=params)
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Cell not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="kpi-service error")

    data = resp.json()
    points = data.get("points", [])
    timestamps = []
    values = []
    for p in points:
        ts_str = p.get("ts")
        val = p.get(kpi)
        if ts_str is not None:
            timestamps.append(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
            values.append(float(val) if val is not None else np.nan)
    return timestamps, np.array(values, dtype=np.float64)


@app.get("/anomalies/cells/{cell_id}", response_model=CellAnomaliesResponse)
async def anomalies_cell(
    cell_id: str,
    kpi: str = Query("dlThroughputMbps", description="KPI name"),
    hours: int = Query(168, ge=1, le=1440, description="Hours of history"),
) -> CellAnomaliesResponse:
    if kpi not in KPI_NAMES:
        raise HTTPException(status_code=422, detail=f"Invalid KPI. Valid: {KPI_NAMES}")

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    from_ts = now - timedelta(hours=max(hours, BASELINE_HOURS))

    async with client_factory() as client:
        try:
            timestamps, values = await _fetch_series(client, cell_id, kpi, from_ts, now)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="kpi-service unreachable") from exc

    if len(values) == 0:
        raise HTTPException(status_code=404, detail="No data for cell")

    return CellAnomaliesResponse(
        cellId=cell_id,
        kpi=kpi,
        from_=since.isoformat().replace("+00:00", "Z"),
        to=now.isoformat().replace("+00:00", "Z"),
        threshold=ANOMALY_Z,
        points=len(values),
        anomalies=[AnomalyPoint(**x) for x in _scan(timestamps, values, since)],  # type: ignore[arg-type]
    )


@app.get("/anomalies", response_model=AggregateAnomaliesResponse)
async def anomalies_aggregate(
    kpi: str = Query("dlThroughputMbps", description="KPI name"),
    hours: int = Query(24, ge=1, le=1440, description="Hours of history"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
) -> AggregateAnomaliesResponse:
    if kpi not in KPI_NAMES:
        raise HTTPException(status_code=422, detail=f"Invalid KPI. Valid: {KPI_NAMES}")

    now = datetime.now(UTC)
    since = now - timedelta(hours=hours)
    from_ts = now - timedelta(hours=max(hours, BASELINE_HOURS))

    all_anomalies: list[AggregateAnomalyItem] = []
    async with client_factory() as client:
        try:
            resp = await client.get(f"{KPI_SERVICE_URL}/kpis/cells")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="kpi-service unreachable") from exc
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="kpi-service error")
        cells = sorted(resp.json(), key=lambda c: str(c.get("cellId", "")))
        for cell in cells[:20]:  # bounded, deterministic scan keeps memory and latency low
            cell_id = cell.get("cellId")
            if not cell_id:
                continue
            try:
                timestamps, values = await _fetch_series(client, cell_id, kpi, from_ts, now)
            except (HTTPException, httpx.HTTPError):
                continue
            for x in _scan(timestamps, values, since):
                all_anomalies.append(
                    AggregateAnomalyItem(cellId=cell_id, region=cell.get("region") or "", **x)  # type: ignore[arg-type]
                )

    # Sort by score desc, then ts desc
    all_anomalies.sort(
        key=lambda x: (-x.score, -datetime.fromisoformat(x.ts.replace("Z", "+00:00")).timestamp())
    )

    return AggregateAnomaliesResponse(kpi=kpi, hours=hours, items=all_anomalies[:limit])


class FaultRequest(BaseModel):
    alarm: dict[str, Any]
    context: dict[str, Any] | None = None


_model: FaultClassifier | None = None
_model_lock = threading.Lock()


def get_model() -> FaultClassifier:
    """Load the classifier by registry name; train a small synthetic one if none exists."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            try:
                _model = FaultClassifier.load(name=MODEL_NAME, models_dir=MODELS_DIR)
            except FileNotFoundError:
                if not AUTO_TRAIN:
                    raise
                from ml_service.train_xgb import train

                logger.info("No registered model in %s; training a synthetic one", MODELS_DIR)
                train(out_dir=MODELS_DIR, register=True)
                _model = FaultClassifier.load(name=MODEL_NAME, models_dir=MODELS_DIR)
    return _model


def _model_or_503() -> FaultClassifier:
    try:
        return get_model()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503, detail="No fault model registered - run make ml-train-xgb"
        ) from exc


@app.post("/predict")
def predict(req: FaultRequest) -> dict[str, Any]:
    """Predict the fault type for one enriched alarm.

    Sync on purpose: FastAPI runs it in a threadpool, so a first-call auto-train
    does not block the event loop.
    """
    return _model_or_503().predict(req.alarm, req.context)


@app.post("/explain")
def explain(req: FaultRequest, top_k: int = Query(5, ge=1, le=20)) -> dict[str, Any]:
    """Top SHAP (TreeSHAP) contributions for the predicted class."""
    return _model_or_503().explain(req.alarm, req.context, top_k=top_k)


def run() -> None:
    import uvicorn

    uvicorn.run("ml_service.api:app", host="0.0.0.0", port=PORT, reload=False)


if __name__ == "__main__":
    run()
