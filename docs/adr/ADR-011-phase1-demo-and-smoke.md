# ADR‑011 – Phase 1 demo and smoke test

**Status:** Accepted  

## Decision
- Provide a single scripted demo path (`make demo`) that runs the full fibre‑cut scenario end‑to‑end.
- Gate the Phase 1 release with a gateway‑only smoke script (`make smoke` / `scripts/smoke.sh`) that exercises the full data path and authentication.

The smoke script performs nine checks through the API gateway:
1. `/healthz` and `/readyz`
2. login (JWT issuance)
3. alarm stream visibility
4. alarm‑storm timeline
5. KPI anomaly detection
6. fault classification badge
7. runbook retrieval
8. Copilot answer that includes runbook citations
9. RBAC enforcement (401 when no token)

Checks are data‑driven: the script polls each endpoint until the expected condition is met or a timeout expires. No fixed sleeps are used.

The `netgen‑simulator` is exempt from `/healthz` because it is a one‑shot job, not a long‑running server.

## Consequences
- The demo path must remain deterministic (seed 42, fibre‑cut at 60× speed) to keep the smoke test reliable.
- Any change to the data flow (e.g., new runbook source) requires updating the smoke expectations.
- The demo script creates topics, back‑fills one day of KPIs, runs the scenario, and performs a quick smoke verification before reporting success.

## Alternatives considered
- **Playwright browser end‑to‑end test** – provides UI coverage but adds heavy dependencies and longer execution time; deferred to Phase 2.
- **Per‑service smoke scripts** – easier to write but would miss integration issues across services.
- **Docker healthchecks only** – verify container liveness but not the functional data path required for the NOC use case.
