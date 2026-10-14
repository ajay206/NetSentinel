# incident-service

W13: consumes `alarms.enriched`, clusters alarms into incidents with topology-aware connected
components over a session window, and publishes them to `incidents`. HTTP on port 8007:
`/healthz`, `/readyz`, `/incidents`, `/incidents/{id}`. See `docs/adr/ADR-012-incident-clustering.md`.
