# ADR-013 – Enterprise RBAC: persisted users, token versions, lockout and audit log
**Status:** Accepted (Step 13b). Extends ADR-003 (gateway auth).

## Context
W11 gave the gateway JWT login with three roles, but users came from an env var (`GATEWAY_USERS`) or built-in demo users with plaintext passwords. It also had:
- no way to change or reset a password;
- no lockout;
- no way to revoke a token before it expires;
- no record of who did what.

Operators also could not act on incidents (acknowledge, assign, resolve). A NOC needs role-specific dashboards, with the server enforcing every rule and not just the UI.

## Decision
- **User store:** the gateway's `UserStore` interface (`services/api-gateway/src/api_gateway/users.py`) has two implementations:
  - `PgUserStore`: tables `ns_users` and `audit_log` in the existing TimescaleDB, created on start. Selected with `USER_STORE=postgres`, the compose default.
  - `MemoryUserStore`: used for tests and DB-less dev.

  Demo or `GATEWAY_USERS` entries are **seeded only when `ns_users` is empty** (first run). Later changes live in the database.
- **Hashing:** bcrypt (cost 10) through the `bcrypt` package. It is a small wheel, needs no passlib, and is preferred over argon2 for image size. The same policy is enforced in the gateway (`password_problems`) and the console (`lib/passwordPolicy.ts`): at least 10 characters with lowercase, uppercase, a digit and a symbol, and it must not contain the username. Seeded demo users keep their weak passwords until they are changed.
- **Token version:** the JWT carries a `tv` claim. The middleware loads the user on every request (2 s in-process cache) and returns **401 "Token revoked"** when the user is missing or disabled, or when `tv` differs. These actions bump `tv`, signing the user out everywhere:
  - a password change (which returns a new token);
  - an admin reset;
  - a role change;
  - disabling the user.

  The **live role** from the database is used, so a demotion applies immediately.
- **Lockout:** after `LOGIN_MAX_FAILURES` (default 5) wrong passwords the account is locked for `LOCKOUT_SECONDS` (default 900). Login then returns **423** even with the right password, until it expires or an admin unlocks it. Unknown users get a plain 401 after a dummy bcrypt check, so response timing does not reveal which usernames exist. The existing per-IP login rate limit still applies.
- **Permissions (server-side):**
  - `/api/admin/*` needs admin.
  - `POST /api/incidents/{id}/actions`, `POST /api/alarms/actions` and `POST /api/copilot/analyze` need operator.
  - Every other `/api` and `/ws` route needs viewer.

  The console hides controls a role lacks (`lib/rbac.ts`), but the gateway returns 403 regardless.
- **Workflow:** incident-service keeps acknowledge, assign, resolve and notes as an overlay next to the deterministic clusterer (in memory, bounded; see ADR-012). The gateway forwards `X-NS-User` and `X-NS-Role`, and incident-service rejects writes without an operator or admin role (defence in depth). A resolve requires a note.
- **Audit:** the gateway writes `audit_log` rows for:
  - logins and lockouts;
  - user created, updated, role changed, unlocked;
  - password changed or reset;
  - every incident and alarm action, including assignee and note.

  It never records passwords, hashes or tokens. Admins read the log at `GET /api/admin/audit`.
- **Admin safety:** an admin cannot change their own role or disable themselves, and the last active admin cannot be demoted or disabled.

## Consequences
- The gateway now depends on Postgres in compose (`ui` profile starts `timescaledb`). Logins return 503 until the store is ready; it retries for about 60 s.
- One indexed primary-key lookup per request, softened by the 2 s cache. A revocation can take up to 2 s to reach another gateway replica, which is acceptable for one gateway.
- Workflow state is lost when incident-service restarts, like the incidents themselves (they are rebuilt by replay). The audit log keeps the history. Persisting workflow is a later step.
- `make reset-db` also wipes users and the audit log, so the demo users are re-seeded.
