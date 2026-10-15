# llm-gateway (W18)

Every LLM call in NetSentinel goes through here: model router (local Ollama first, cloud stub
until Phase 3), prompt-injection guard, PII redaction, timeouts, a circuit breaker and
per-caller tokens / rate / concurrency limits. See ADR-018 and `docs/handbook/03-services.md`.

```bash
uv run uvicorn llm_gateway.main:app --port 8010
uv run pytest services/llm-gateway -k redteam    # evals/redteam.jsonl
```
