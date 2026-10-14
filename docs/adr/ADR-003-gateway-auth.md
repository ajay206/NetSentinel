# ADR 003 – API Gateway Authentication

**Status:** Draft

## Context
Week 2 requires a visible dashboard quickly. The team needs a thin gateway to expose alarm data to the UI without the overhead of full‑blown authentication mechanisms. The data is synthetic and only used in development environments.

## Decision
Implement a lightweight FastAPI gateway (`services/api-gateway`) that:

* Listens on `0.0.0.0:8000`.
* Exposes health, alarm retrieval, and WebSocket endpoints.
* **Does not** enforce any authentication or authorization.
* Is bound to localhost in development (via Docker compose port mapping) and will later be fronted by Traefik.

Authentication and RBAC will be introduced in **Week 11** when Traefik is added.

## Consequences
* Simplicity: developers can start the UI immediately.
* Security: the endpoint is open; it must never be exposed in production without a reverse proxy.
* Future work: when Traefik is added, replace the open endpoints with JWT‑based auth and enforce role checks.

## Alternatives Considered
* **Traefik now** – would add complexity and require secret management early.
* **Shared secret** – a simple API key could be added now, but it was deemed unnecessary for a purely synthetic demo.
