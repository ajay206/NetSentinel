# ADR 009 – Simple Copilot with a Local LLM

**Status:** Accepted  
**Date:** 2026-10-14  

## Context
The NetSentinel NOC demo needs an AI‑assisted “Copilot” that can analyse recent alarms and KPI anomalies for a given site and suggest a root cause and remediation steps. The solution must run entirely on‑premise, use synthetic data only, and avoid external API calls. The build plan keeps W9 deliberately simple: LangGraph and hosted LLM APIs would add complexity, cost and data-exfiltration risk at this stage.

## Decision
Implement a lightweight, pure‑Python async service (`copilot-orchestrator`) that talks to a local Ollama instance. The service:

* Exposes a FastAPI endpoint `POST /analyze`.
* Retrieves enriched alarms, KPI anomalies, fault‑type predictions and runbooks from existing internal services.
* Calls the local Ollama model (`qwen2.5:1.5b` by default) via its `/api/chat` endpoint, requesting a structured JSON answer.
* Validates the answer with a strict Pydantic schema; on validation failures it retries up to three times, feeding back the errors.
* Falls back to a deterministic answer when the LLM is unreachable or after exhausting retries.
* Propagates upstream failures as warnings, never as hard errors.

All upstream calls are mocked in CI; no real LLM is ever contacted during automated testing.

## Consequences
* **Pros**
  * Zero external network traffic – data stays inside the demo environment.
  * Predictable resource usage (128 MiB memory limit, model size ~1 GiB).
  * Simple deployment via Docker Compose with `extra_hosts: host.docker.internal`.
  * Deterministic fallback guarantees a response even when the model fails.

* **Cons**
  * The chosen 1.5 B model may produce occasional hallucinations; the retry/validation loop mitigates this but cannot eliminate it completely.
  * No LangGraph orchestration – future extensions may need to refactor the flow.
  * Limited to synthetic data; performance numbers are not yet measured against a real LLM.

## Alternatives Considered
| Alternative | Reason for Rejection |
|-------------|----------------------|
| **LangGraph orchestration** | Added unnecessary complexity for a demo that only needs a single LLM call. |
| **Hosted LLM API (e.g., OpenAI, Anthropic)** | Would expose production‑like data outside the box and incur cost. |
| **Free‑text answer + regex parsing** | Fragile parsing, higher risk of missed or malformed fields. |
| **No fallback, error‑only response** | Would break the UI when the model is unavailable; the demo must always show a result. |
