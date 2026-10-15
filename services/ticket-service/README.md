# ticket-service (W16)

Ticket drafts with a human approval workflow (`draft → approved | rejected`) and an append-only,
hash-chained audit log. AI (the MCP `open_ticket_draft` tool) may draft; only operators approve.
Reached through the gateway (`/api/tickets/*`). See `docs/handbook/03-services.md` and ADR-016.

```bash
cd services/ticket-service && uv run alembic upgrade head   # DATABASE_URL, default sqlite
uv run uvicorn ticket_service.main:app --port 8009
```
