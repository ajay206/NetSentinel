# ADR-003 – Gateway Authentication and RBAC (W11)

**Status:** Accepted (final, W11; supersedes the W2 draft)  
**Context:**  
- W2 shipped an open FastAPI gateway (`services/api-gateway`).  
- The original plan for W11 was “Traefik + JWT”.  

**Decision:**  
Keep authentication **inside** the FastAPI gateway as a pure ASGI middleware rather than adding a Traefik ForwardAuth container.

**Rationale**
- Reduces the number of containers on an 8 GB Mac development box.
- The gateway already terminates WebSockets and proxies all internal services.
- Authentication logic is unit‑testable with pytest.
- Traefik ForwardAuth can be added later in front of the gateway without changing token format.

**Implementation Details**

| Aspect | Details |
|--------|---------|
| **JWT algorithm** | HS256 (PyJWT) |
| **Issuer** | `netsentinel-gateway` |
| **Claims** | `sub`, `role`, `iat`, `exp`, `iss` |
| **TTL** | 8 h (`JWT_TTL_SECONDS` env var) |
| **Secret** | `JWT_SECRET` from environment. If unset, a random per‑process secret is generated and a warning is logged. If length < 32 chars, a warning is emitted. |
| **User source** | `GATEWAY_USERS` env var: `name:password:role,...`. Demo users (`viewer`, `operator`, `admin`) are added when `DEMO_USERS=1`. Demo passwords are the same as usernames (plaintext acceptable only for local demo). Production should replace this with an IdP/OIDC. |
| **Roles hierarchy** | `viewer` < `operator` < `admin` |
| **Public endpoints** | `GET /health`, `GET /docs`, `GET /openapi.json`, `OPTIONS *`, `POST /api/auth/login` |
| **RBAC** | - `POST /api/copilot/analyze` → `operator`<br>- `GET /api/auth/users` → `admin`<br>- All other `/api/*` and `/ws/*` → `viewer` |
| **WebSocket auth** | Token supplied via query param `?token=` (browsers cannot set headers). Invalid/expired token results in close codes: 4401 (unauthenticated), 4403 (forbidden), 4429 (rate‑limited). |
| **Service‑to‑service auth** | Internal callers (`copilot-orchestrator`, `mcp-server`) send `GATEWAY_SERVICE_TOKEN`. This token maps to a synthetic principal `service` with role `viewer`. |
| **Rate limiting** | Sliding‑window (60 s) in‑memory counters per user:<br>• `RATE_LIMIT_PER_MIN` (default 600) → 429 + `Retry-After`<br>Login endpoint limited per IP: `LOGIN_RATE_PER_MIN` (default 10). |
| **Escape hatch** | `AUTH_DISABLED=1` disables all checks – intended for tests only. |
| **Frontend handling** | The console stores the JWT in `sessionStorage` (not `localStorage`). It sends the token as `Authorization: Bearer <jwt>` on all `/api` calls. Any 401 response forces a redirect to the login screen. |

**Consequences**
- Simpler local development stack.
- Tokens are portable; a future Traefik ForwardAuth layer can validate the same JWTs without modification.
- No external IdP; demo‑only plaintext passwords are acceptable only in the local demo environment.

**Alternatives Considered**
- **Traefik ForwardAuth** – would add another container and complexity; not needed for the current resource constraints.
- **Full OIDC/Keycloak** – provides robust identity management but exceeds the 8 GB RAM budget for local development.
- **Cookie‑based auth + CSRF** – unnecessary for a pure API gateway; JWTs are sufficient for both HTTP and WebSocket flows.

