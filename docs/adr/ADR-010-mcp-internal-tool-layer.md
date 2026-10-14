# ADR 010 – Internal MCP Tool Layer for NetSentinel (W10)

**Status:** Accepted  
**Date:** 2026-10-14  

## Context
NetSentinel’s Copilot orchestrator needs a reliable, observable way to invoke backend tools (alarms, KPI anomalies, runbook search, fault prediction). Phase 9 used direct HTTP calls to each service. For Phase 10 we introduce a thin internal service – **mcp-server** – that aggregates these tools behind a single, streamable‑HTTP endpoint (`POST /mcp`).  

Key constraints:
- Must remain internal to the NOC; no external AI clients.
- Use the official MCP Python SDK **v1** (FastMCP) to avoid breaking changes in SDK v2.
- Authentication via a bearer token (`MCP_SERVICE_TOKEN`) enforced by a constant‑time ASGI middleware.
- Stateless HTTP transport; JSON request/response payloads.
- Service runs in Docker with limited memory (128 MiB) and no published ports; reachable only from other compose containers.

## Decision
Create `mcp-server` as a new Docker service (port 8006) that:
1. Exposes a single POST `/mcp` endpoint handling all tool calls.
2. Authenticates every request with `Authorization: Bearer $MCP_SERVICE_TOKEN`. Missing or invalid token yields **401**; the service aborts startup if the token is unset unless `MCP_ALLOW_NO_TOKEN=1` (local dev convenience).
3. Implements an app‑factory pattern (`uvicorn --factory mcp_server.app:build_app`) to allow lazy creation of an MCP session per Copilot `/analyze` request.
4. Returns a response that includes a `toolCalls` array, each entry containing:
   - `name` – tool name
   - `ok` – boolean success flag
   - `durationMs` – elapsed time
   - `transport` – `"mcp"` (internal) or `"http"` (fallback direct HTTP)

over the Phase 1 services. Backend failures map to MCP tool errors (`isError: true`) without leaking internal URLs. The copilot opens one MCP session per `/analyze` request and records every call in its own `toolCalls` field.

## Consequences
* **Positive**
  - Single point of observability for tool latency and failures.
  - Uniform authentication and error handling.
  - Keeps the W9 HTTP path behind TOOLS=http, so the MCP layer can be turned off.
* **Negative**
  - Adds a network hop for each tool call.
  - Requires additional Docker service and contract generation steps.
* **Mitigations**
  - Service runs on the same Docker network; latency is negligible.
  - Contract files (`contracts/mcp/netsentinel-tools.json`, `contracts/openapi/copilot-orchestrator.yaml`) are regenerated automatically via `make mcp-contract` and `make copilot-contract`.

## Alternatives Considered
| Alternative | Reason for Rejection |
|-------------|----------------------|
| Keep direct HTTP calls (Phase 9 path) | Duplicates authentication logic, loses unified latency reporting, and makes future SDK migration harder. |
| Upgrade immediately to MCP SDK v2 (renamed `MCPServer`) | SDK v2 introduces breaking API changes; pinning `<2` lets us migrate gradually while keeping existing tool wrappers stable. |
| Use stdio transport (e.g., Unix sockets) | Rejected because the service must be reachable from multiple containers and future scaling may require networked deployment. |
| Expose MCP to external AI clients | Out of scope; only the copilot is a client, and Phase 2 tools (query_topology, open_ticket_draft) land later. |

