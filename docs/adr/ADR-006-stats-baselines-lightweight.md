# ADR 006 – Lightweight Statistical Baselines for Anomaly Detection
**Status:** Accepted  
**Date:** 2026-10-14  

## Context
The platform needs a fast, low‑memory statistical baseline for the new **ml‑service**.  
Constraints:

* The service runs in a tiny container (256 MiB) on a Mac with only 8 GB RAM.  
* We avoid heavy Python libraries (statsmodels, pandas, Prophet) to keep the 8 GB Mac and the 256 MB container budget comfortable.
* The service must be able to run even when MLflow is not installed.  
* KPIs are fetched from the existing **kpi‑service** over HTTP; there is no shared database.  
* Anomalies are computed on‑demand per request – we do not store them yet.

## Decision
* **Decomposition** – Implement a custom STL‑like seasonal decomposition in pure NumPy/SciPy (`baselines.py`).  
  * Trend = centred rolling median over one day (96 × 15 min points).  
  * Seasonal = per‑phase median of detrended values, also centred.  
  * Residual = original – trend – seasonal.  
  * If < 2 days of data are available, fall back to a 3 h rolling median trend and omit the seasonal term.

* **Anomaly scoring** – Combine a robust Z‑score with a two‑sided CUSUM detector.  
  * Robust Z‑score: `(x - median) / (1.4826 * MAD)`. If MAD = 0, use `mean absolute deviation * 1.2533`.  
  * CUSUM: `k = 0.5`, `h = 5` applied to the robust Z‑score series.  
  * An anomaly is flagged when `|z| > ANOMALY_Z` (default 3.5) **or** when CUSUM raises an alarm.  
  * Detection mode can be `zscore`, `cusum`, or `both`; direction can be `high`, `low`, or `both`.

* **MLflow optionality** – The service declares an extra optional dependency `mlflow-skinny`.  
  * If `MLFLOW_TRACKING_URI` is set **and** the package is importable, runs are logged to MLflow.  
  * Otherwise, runs are written as JSON files under `evals/runs/<experiment>-<UTC>.json`. The directory is git‑ignored.

* **Service architecture** – `ml-service` is a FastAPI app (port 8003, compose profile **pipeline**) that:
  * Depends on `kpi-service` (HTTP API) for KPI data.  
  * Exposes health/readiness endpoints and anomaly query endpoints.  
  * Performs decomposition and scoring **per request**; no persistent anomaly store.

## Consequences
* **Low memory footprint** – Pure NumPy/SciPy fits comfortably in the 256 MiB limit.  
* **Deterministic baselines** – Rolling‑median based trend/seasonal components are reproducible across runs.  
* **Limited statistical power** – Without statsmodels/Prophet we lose sophisticated modelling (e.g., ARIMA, holiday effects).  
* **No persisted anomalies** – Downstream consumers must request anomalies each time; future steps will add a storage layer (DB table or Kafka topic).  
* **MLflow fallback** – Teams can still inspect experiment artefacts even on machines without MLflow.

## Alternatives Considered
| Alternative | Pros | Cons |
|-------------|------|------|
| **statsmodels STL** | Well‑tested, handles missing data, automatic seasonality detection. | Pulls in pandas & statsmodels → > 500 MiB memory, exceeds container limits. |
| **Prophet** | Handles holidays, trend changepoints. | Heavy dependency chain, requires PyStan, not feasible on 8 GB Mac. |
| **Store anomalies in a DB / Kafka** | Immediate availability for other services. | Adds operational complexity; not needed for the MVP week. |

The lightweight NumPy approach satisfies the MVP timeline while keeping the service portable and fast.
