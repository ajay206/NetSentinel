# 04 - Kafka Topics & Data Models

## Kafka Topics Inventory (Week 2)

| Topic        | Partitioner Key | Replication Factor | Retention | Description |
|--------------|-----------------|--------------------|-----------|-------------|
| `alarms.raw` | `siteId`        | 1                  | 7 days    | Synthetic fault alarms emitted by **netgen‑simulator**. |
| `alarms.enriched` | `siteId`   | 1                  | 7 days    | Alarms after enrichment (future service). |
| `kpis`       | `siteId`        | 1                  | 7 days    | KPI telemetry (future service). |
| `incidents`  | `incidentId`    | 1                  | 7 days    | Correlated incidents (future service). |

### `alarms.raw` Schema (TMF642‑like)

| Field                | Type    | Description |
|----------------------|---------|-------------|
| `id`                 | `string` (UUID) | Unique alarm identifier. |
| `href`               | `string` | REST link to the alarm resource (`/alarm/{id}`). |
| `alarmType`          | `string` | E.g. `communicationsAlarm`. |
| `perceivedSeverity` | `string` (enum) | `critical`, `major`, `minor`, `warning`, `cleared` (X.733). |
| `probableCause`      | `string` | High‑level cause category (e.g. `lossOfSignal`). |
| `specificProblem`   | `string` | Human‑readable description (e.g. `LOS`). |
| `alarmedObject`      | `object` | `{ "id": "<siteId>", "@referredType": "Site" }`. |
| `siteId`             | `string` | Redundant key for partitioning; matches `alarmedObject.id`. |
| `alarmRaisedTime`   | `string` (ISO‑8601) | Timestamp when alarm was raised. |
| `state`              | `string` (enum) | `raised` or `cleared`. |
| `sourceSystemId`    | `string` | Identifier of the producer (`netgen-simulator`). |
| `@type`              | `string` | Fixed value `"Alarm"` for JSON‑LD style. |

**Example JSON alarm (fibre_cut scenario):**

```json
{
  "id": "c1b2d3e4-5678-90ab-cdef-1234567890ab",
  "href": "/alarm/c1b2d3e4-5678-90ab-cdef-1234567890ab",
  "alarmType": "communicationsAlarm",
  "perceivedSeverity": "critical",
  "probableCause": "lossOfSignal",
  "specificProblem": "LOS",
  "alarmedObject": {
    "id": "SITE-003",
    "@referredType": "Site"
  },
  "siteId": "SITE-003",
  "alarmRaisedTime": "2026-10-14T08:45:11Z",
  "state": "raised",
  "sourceSystemId": "netgen-simulator",
  "@type": "Alarm"
}
```

*Key:* `siteId` – ensures all alarms for the same site land in the same partition, enabling ordered processing per site.

### Producer & Consumer Details

* **Producer (netgen‑simulator)** – Uses `aiokafka.AIOKafkaProducer`. The key is the UTF‑8 encoded `siteId`. JSON payload is `json.dumps(alarm).encode('utf‑8')`.
* **Consumer (api‑gateway)** – `aiokafka.AIOKafkaConsumer` with `group_id="gateway-alarms"` and `auto_offset_reset="latest"`. Consumes messages, stores the latest 100 in an in‑memory list, and pushes each new alarm to connected WebSocket clients.
* **WebSocket Envelope** – Every message sent over `/ws/alarms` is wrapped:

  ```json
  // Snapshot (sent once on connect)
  {
    "type": "snapshot",
    "alarms": [ /* array of latest alarm objects */ ]
  }

  // Incremental alarm
  {
    "type": "alarm",
    "alarm": { /* single alarm object as defined above */ }
  }
  ```

Other topics (`alarms.enriched`, `kpis`, `incidents`) are defined but their schemas are **TBD** and will be added in later weeks.

--- 

*The schema and envelope definitions are now part of the official documentation so that any new consumer can be built with confidence.*
