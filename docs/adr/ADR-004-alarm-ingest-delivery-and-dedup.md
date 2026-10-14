# ADR 004 – Alarm Ingest Delivery and De‑duplication

**Status:** Accepted  
**Date:** 2026-10-14  

## Context
During Week 4 we introduced a new service `services/alarm-ingest` that consumes the raw alarm Kafka topic, normalises, enriches, de‑duplicates and correlates alarms before publishing them to `alarms.enriched`. The service runs with FastAPI on port 8001 and uses `aiokafka` for Kafka interaction.

The system must guarantee that every valid alarm is eventually published, while tolerating occasional duplicates caused by at‑least‑once delivery semantics. Down‑stream consumers (gateway, console) are expected to be idempotent by using the de‑duplication key.

## Decision
* **Delivery semantics:** At‑least‑once. The consumer commits offsets **only after** the enriched message has been successfully produced with `acks=all`. This gives us reliable delivery without the complexity of exactly‑once transactions.
* **Idempotency:** Down‑stream consumers use `dedup.key` (`siteId|alarmType|probableCause|specificProblem`) to collapse repeats: the console replaces the row with the same key instead of adding a new one. The Kafka message key is `siteId`, so all alarms of one site stay in order on one partition.
* **In‑memory state:** De‑duplication and correlation windows are kept in memory for the duration of the process. Persistence is deferred to a later sprint (e.g., Redis or RocksDB). Restarting the service clears the windows; re‑processing of the raw topic may therefore re‑emit some alarms, which is acceptable because downstream is idempotent.
* **Topology source:** A deterministic seed (default 42) is used to generate a small topology JSON file at build time. The service loads this file directly instead of calling a separate topology‑service, which is not yet built.
* **Error handling:** Invalid raw alarms are counted in `stats.invalid` and dropped. They never reach the enriched topic.

## Consequences
* **Pros**
  * Simpler implementation – no need for transactional producers or external state stores.
  * Guarantees that no valid alarm is lost.
  * Down‑stream services can be written without complex retry logic.

* **Cons**
  * Duplicate messages may appear after a restart or a consumer rebalance.
  * In‑memory windows mean that long‑running deduplication (beyond the process lifetime) is not possible yet.
  * `GET /stats` exposes `duplicates` and `invalid` so the impact is visible.

## Alternatives Considered
| Alternative | Description | Why Rejected |
|-------------|-------------|--------------|
| Exactly‑once Kafka transactions | Producer uses `transactional.id` and commits offsets in the same transaction. | Adds considerable complexity, requires idempotent producer state, and was out of scope for the sprint. |
| Auto‑commit | Let the consumer auto‑commit offsets. | Would acknowledge messages before they are successfully published, risking data loss on failure. |
| External persistent store for deduplication | Use Redis or a DB to keep dedup keys across restarts. | Not required for the MVP; would increase operational overhead. |
