# NetSentinel MCP Server

FastMCP tools exposing Phase 1 services (Gateway, ML, RAG) for network operations.

## Tools

- `get_alarms(site_id: str, window_minutes: int = 30)` — Recent enriched alarms for a site
- `kpi_anomalies(site_id: str, hours: int = 1)` — KPI anomalies for a site's cells
- `search_runbooks(query: str, fault_type: str | None = None, top_k: int = 3)` — Search runbooks
- `predict_fault(alarm: dict)` — Predict fault type from alarm

## Resource

- `runbook://{runbook_id}` — Runbook markdown content

## Prompt

- `analyze_site(site_id: str, window: str = "30m")` — Guided site analysis workflow

## Run (dev)

```bash
uv run mcp dev services/mcp-server/src/mcp_server/server.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_URL` | `http://localhost:8000` | Gateway service base URL |
| `ML_SERVICE_URL` | `http://localhost:8003` | ML service base URL |
| `RAG_SERVICE_URL` | `http://localhost:8004` | RAG service base URL |
| `MCP_SERVICE_TOKEN` | *required* | Bearer token for /mcp endpoint |
| `MCP_ALLOW_NO_TOKEN` | `0` | Set to `1` to allow running without token (dev only) |
