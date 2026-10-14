# ADR-012 – Topology-aware incident clustering
**Status:** Accepted

## Context
The incident-service must group enriched alarms into incidents that reflect the underlying network topology. Simple time‑bucket aggregation cannot capture relationships across sites, while machine‑learning approaches add unnecessary complexity. Deterministic clustering is required so that a service restart replays the same alarms and produces identical incidents.

## Decision
Implement a session‑window, topology‑aware clustering algorithm (IncidentClusterer) in `clustering.py`:

* **Windowing:** Event‑time session window with gap `INCIDENT_GAP_SECONDS` (default 300 s). An alarm joins an open incident if the absolute difference between the alarm timestamp and the incident’s `lastSeen` is ≤ gap.
* **Topology relation:** An alarm is related to an incident when its site is:
  * the same site as any alarm in the incident, or
  * directly linked to an incident site (e.g. both ends of a cut link), or
  * within `INCIDENT_MAX_HOPS` (default 4) hops as an ancestor/descendant, or
  * a sibling under a shared non‑core ancestor (hub). Core sites are excluded as shared ancestors.
* **Merging:** If an alarm matches multiple open incidents, merge them into the oldest incident.
* **Cleared alarms:** Only update `lastSeen` of the matching incident; they never create new incidents.
* **Incident ID:** `"INC-" + first‑10‑hex‑digits(uuid5(first_alarm_id))` (uppercase).
* **Root site selection:** Choose the member closest to the core (minimum depth). Ties are broken by worst severity, earliest timestamp, then site identifier.
* **Late events:** Accepted if they fall within the gap window.
* **Retention:** Keep at most `INCIDENT_MAX_KEEP` (500) incidents; older ones are pruned.

The service consumes `alarms.enriched` without a consumer group, starting from the earliest offset, guaranteeing deterministic replay.

## Alternatives considered
| Alternative | Description | Reason for rejection |
|-------------|-------------|----------------------|
| Fixed time buckets | Group alarms into static 5‑minute windows. | Ignores topology; cannot merge related alarms that span bucket boundaries. |
| ML clustering | Use a trained model to infer incident boundaries. | Adds operational complexity, non‑deterministic results, and requires labeled data. |
| Consumer group with committed offsets + persisted state | Track progress and store incident state externally. | Breaks deterministic replay; state drift can cause different incident sets after restarts. |

## Consequences
* **Determinism:** Restarting the service replays the same alarms in the same order, yielding identical incidents.
* **Measured performance:**  
  * *Sequential faults:* 397 alarms → 79 incidents, compression 5.03×, root match 100 %, purity 95 %, completeness 100 %, deterministic True.  
  * *Concurrent pairs:* 48 incidents, compression 8.27×, root match 65 %, merged 9 incidents, deterministic True.  
  * *Concurrent with 60 s gap:* 90 incidents, compression 4.41×, root match 65 %, split 1, merged 9.
* **Limitation:** Time‑plus‑topology clustering cannot separate simultaneous nearby faults; Phase 2 RCA will need link‑path evidence to split such incidents.
* **Operational impact:** Requires the `ops` compose profile, 128 MiB memory, and the `incidents` Kafka topic (consumers keep the latest `version` per key; log compaction is a later option). Replay depends on `alarms.enriched` retention.
