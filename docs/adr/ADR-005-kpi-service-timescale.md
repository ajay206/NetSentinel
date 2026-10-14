# ADR 005 – KPI Service Persistence in TimescaleDB

**Status:** Accepted  
**Date:** 2026-10-14  

## Context
The KPI service (FastAPI, port 8002) must ingest high‑volume KPI samples from the `kpis` Kafka topic, store them efficiently for time‑series queries, and expose read‑only endpoints for the NOC console.  

Key constraints:

* Operators view timestamps in Indian Standard Time (IST) while the database stores UTC.
* The service must guarantee **at‑least‑once** delivery from Kafka but also be safe against duplicate processing.
* The overall architecture follows a *database‑per‑service* rule – only the KPI service may touch the `kpi_samples` table.
* Deployment is containerised with Docker‑Compose; the TimescaleDB instance already exists in the `timescaledb` container.

## Decision
1. **TimescaleDB Hypertable**  
   * Create a hypertable `kpi_samples` (PK = `(cell_id, ts)`) with 1‑day chunks.  
   * Add indexes on `cell_id` and on `ts DESC` to support the most common query patterns.  
   * The KPI service owns the table; no other service may read/write it directly.

2. **Migrations**  
   * Use plain SQL migration files located in `src/kpi_service/migrations`.  
   * At service start‑up, the migrations are applied in order and a record is inserted into the `schema_migrations` table.  
   * No Alembic integration yet – keeping the migration process simple and deterministic.

3. **Kafka Consumption Guarantees**  
   * Consumer group `kpi-service`, `auto.offset.reset=earliest`.  
   * Manual commit after a batch has been successfully written to the DB – this yields **at‑least‑once** semantics.  
   * Inserts are idempotent via `ON CONFLICT (cell_id, ts) DO NOTHING`. Duplicate messages are therefore harmless.

4. **Gateway Interaction**  
   * The API‑gateway forwards only the read‑only KPI endpoints (`/api/kpi/cells*`) to the KPI service.  
   * The gateway never writes to TimescaleDB; all writes are confined to the KPI service.

5. **Chart Rendering**  
   * The NOC console renders KPI charts as inline SVG generated on‑the‑fly.  
   * This avoids pulling in heavy charting libraries (e.g., ECharts) and keeps the bundle size and RAM usage low.

## Consequences
* **Operational Simplicity** – One service owns the time‑series table, making backup/restore and scaling decisions straightforward.  
* **Idempotent Writes** – Duplicate Kafka messages do not corrupt data, but they do increase consumer lag if the replay rate is high.  
* **Limited Migration Tooling** – Plain SQL migrations lack the richer features of Alembic (downgrades, version branching). Future migration strategy will need to be revisited.  
* **No Continuous Aggregates** – Aggregations are performed on‑the‑fly using `time_bucket`. This is acceptable for the current query volume but may become a bottleneck if query load grows.  
* **Chart Fidelity** – Inline SVG provides basic line charts; advanced interactions (zoom, tooltip) are not available without a full‑featured library.

## Alternatives Considered
| Alternative | Reason for Rejection |
|-------------|----------------------|
| **Alembic migrations** | Adds another dependency and complexity; the team preferred a minimal, file‑based approach for the initial rollout. |
| **ECharts / Chart.js** | Increases bundle size (~1 MB) and RAM consumption on the console, which runs on low‑spec machines. |
| **Continuous aggregates in TimescaleDB** | Would require additional materialized hypertables and refresh policies; postponed until query performance proves insufficient. |
| **Writing directly from the API‑gateway** | Violates the database‑per‑service rule and would couple the gateway to TimescaleDB, making future refactors harder. |

---  
*Prepared by the KPI Service team.*
