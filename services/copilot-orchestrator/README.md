# copilot-orchestrator

Simple copilot service that gathers evidence from upstream services, queries a local Ollama LLM for a structured JSON answer, validates with Pydantic, enforces citations, retries on invalid responses, and falls back to a deterministic answer if the LLM is unavailable.

## Endpoints

- `GET /healthz` — liveness probe
- `GET /readyz` — readiness probe (includes LLM status)
- `POST /analyze` — analyze a site (body: `{site_id, window?}`)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_URL` | `http://localhost:8000` | API Gateway base URL |
| `ML_SERVICE_URL` | `http://localhost:8003` | ML Service base URL |
| `RAG_SERVICE_URL` | `http://localhost:8004` | RAG Service base URL |
| `LLM_GATEWAY_URL` | `http://localhost:8010` | llm-gateway base URL (Step 18: the only path to a model) |
| `LLM_GATEWAY_TOKEN` | unset | Caller token registered in llm-gateway `LLM_GATEWAY_CALLERS` |
| `LLM` | `gateway` | `gateway`, or `off` (deterministic fallback only) |
| `PORT` | `8005` | Server port |
