# ADR-016 – Ticket drafts with human approval and an append-only audit log
**Status:** Accepted (Step 16). Builds on ADR-010 (MCP tool layer) and ADR-013 (RBAC and audit).

## Context
The copilot can now explain an incident and cite evidence (W9–W15). The next step is opening trouble tickets, but a ticket dispatches field teams and costs money. The build plan (W16) asks for drafts, a draft → approved/rejected workflow, an append-only audit log and an `open_ticket_draft` MCP tool. It is done when only operators can approve, every state change is audited, MCP creates drafts only, and the console queue works end to end.

## Decision
- **Separate ticket-service** (FastAPI, SQLAlchemy Core, Alembic migrations) on the existing TimescaleDB/Postgres (`ops` profile), with SQLite for dev and tests. No new database container.
- **AI drafts, humans decide.** The service token (used by MCP and the copilot) is a viewer that has exactly one write: `POST /api/tickets/drafts`. There is no approve tool in MCP. Approve and reject need the operator role at the gateway, and ticket-service checks the role again. A shared `TICKET_SERVICE_TOKEN` stops forged identity headers.
- **State machine:** a decision is a single conditional `UPDATE … WHERE status='draft' [AND version=?]`, so concurrent approvals cannot both win (409). Reject needs a note.
- **Audit:** `ticket_audit` is written in the same transaction as the state change. It is protected by a DB trigger that rejects UPDATE/DELETE and by a SHA-256 hash chain (`prev_hash` → `hash`, writers serialised by a Postgres advisory lock). `GET /audit/verify` recomputes the chain. The gateway's own `audit_log` also records who did it.

## Alternatives considered
- **Tickets inside incident-service:** fewer services, but it mixes clustering with approval and the audit trail. The plan names ticket-service.
- **Event sourcing on Kafka:** a natural append-only log, but the approval queue needs consistent reads and the extra replay code was not worth it.
- **Four-eyes rule (the creator cannot approve):** not adopted, because single-operator demos would break. The audit trail records the creator and the approver; this can be turned on later.

## Consequences
- Every state change is reconstructable and tamper-evident. A DBA can still drop the trigger, but `verify` then fails.
- The `ops` profile now starts TimescaleDB (+512 MB).
- **Deferred:** pushing approved tickets to an external ITSM. "Approved" is final within NetSentinel.
