# 04 - Kafka Topics & Data Models

## Kafka Topics Inventory
NetSentinel uses 4 core Kafka topics managed by `scripts/create_topics.sh`:
1. `alarms.raw`: Ingested raw telemetry and fault alarms from network simulation. (Partitioned by `siteId`, RF=1, retention=7 days).
2. `alarms.enriched`: Processed alarms enriched with topological and contextual metadata. (Partitioned by `siteId`, RF=1, retention=7 days).
3. `kpis`: Performance metrics and KPI threshold violations. (Partitioned by `siteId`, RF=1, retention=7 days).
4. `incidents`: Correlated multi-alarm incidents requiring operator intervention. (Partitioned by `incidentId`, RF=1, retention=7 days).

## Message Schemas (Status: Not Yet Defined)
* **Current Status:** Strict Pydantic message schemas are **not yet defined** in Week 1. They will be implemented in subsequent weeks as producer and consumer services are built.
* **Planned Alarm Standard (TMF642):** Alarms will adhere closely to the **TM Forum TMF642 Alarm Management API** specification format (adapted for synthetic telecom events), including fields such as:
  * `alarmId`: Unique identifier
  * `alarmType`: (e.g., QualityOfService, ProcessingError, EquipmentAlarm)
  * `perceivedSeverity`: (Critical, Major, Minor, Warning, Cleared - based on X.733)
  * `probableCause`: Specific root cause category
  * `siteId`: Identifier for the affected cell site / equipment
  * `eventTime`: ISO-8601 timestamp
  * `specificProblem`: Detailed textual description
