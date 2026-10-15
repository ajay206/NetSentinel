# ADR-018: llm-gateway, one service for every model call (router + guardrails)

- **Status:** Accepted (Step 18, W18)
- **Context:** The copilot (W9 analyze, W17 RCA agent) called Ollama directly. Phase 3 adds
  TelcoGPT-mini and possibly a cloud model, and untrusted text (alarm notes, runbook snippets)
  flows straight into prompts. Routing, limits, PII handling and injection defence need to
  live in one place.

## Decision

1. **`services/llm-gateway`** (FastAPI, port 8010, `copilot` profile, internal only) owns the
   only model client. `POST /v1/complete {messages, schema?, route?}` returns
   `{content, route, model, latencyMs, attempts, caller, redactions}`. CI enforces this with
   `scripts/check_llm_calls.py`, a grep for the Ollama port, its API paths, `OLLAMA_URL` and
   cloud LLM hosts outside `services/llm-gateway`.
2. **Router:** `LLM_ROUTES` is an ordered list. The default `ollama:qwen2.5:1.5b,cloud:stub`
   tries the local SLM first. `cloud:stub` never leaves the box and always fails, keeping the
   slot ready for `telcogpt-mini` in Phase 3 with no paid API. Each route has a timeout and a
   **circuit breaker** (open after `LLM_BREAKER_FAILURES` failures, half-open after
   `LLM_BREAKER_COOLDOWN_S`), so a dead Ollama fails fast instead of eating every timeout.
3. **Prompt-injection guard** (`guard.py`): deterministic, explainable rules check every
   non-system turn, including base64-wrapped payloads. The rules cover instruction override,
   role hijack, prompt/secret exfiltration, tool hijack ("approve without review") and chat
   template tokens. A hit returns **400 `prompt_injection`** before any model call, and the
   copilot falls back to its deterministic, cited answer. The caller's own system prompt is
   trusted. A classifier model was rejected for now: it adds a model dependency and is not
   explainable, and the rules are measured against a red-team set instead.
4. **PII redaction** (`pii.py`): typed placeholders (`<EMAIL_1>`, `<IMSI_1>`, ...) replace PII
   in untrusted turns before the model (`LLM_REDACT_PROMPTS=1`), in completions and in logs.
   Types: EMAIL, PHONE, IP_ADDRESS, IMSI, IMEI (Luhn or keyword), CREDIT_CARD (Luhn), PERSON
   (after a title or role word). The default engine is regex, tuned so NOC ids (`SITE-010-N1-C2`,
   `alm-root-0001`, `RB-FIB-001`), timestamps and KPIs pass untouched. **Presidio** is an
   optional engine (`PII_ENGINE=presidio`, when `presidio-analyzer`/`-anonymizer` and a spaCy
   model are installed). It is not a default dependency because the spaCy model costs hundreds
   of MB per multi-arch image, and its NER over-redacts NOC ids. This deviates from the build
   plan's `uv add presidio-*` and is recorded here.
5. **Per-caller limits:** `LLM_GATEWAY_CALLERS=name:token:rpm` registers bearer tokens.
   Requests over the limit get 429 (requests per minute), 413 (prompt size,
   `LLM_MAX_PROMPT_CHARS`) or wait on a concurrency semaphore (`LLM_CALLER_CONCURRENCY`). With
   no callers configured the gateway runs in dev mode, and `/v1/stats` reports `devBanner`.
6. **Visibility:** `/analyze` returns `llm {route, latencyMs, redactions, blocked}`. The console
   shows a **model-route chip**, a "PII redacted" marker and a "guard blocked" chip. The W17
   trace view's RCA tool call is named `llm:<route>` and carries the gateway latency.

## Consequences

- One hop more (~1 ms locally). Model swaps in Phase 3 only change `LLM_ROUTES`.
- Heuristic guards have false negatives: `evals/redteam.jsonl` (48 cases: 18 injection,
  18 PII, 12 tricky benign NOC lines) runs in CI (`uv run pytest services/llm-gateway -k
  redteam`) and grows with every miss. The human approval node (ADR-016/017) remains the
  final control for actions.
- Redaction before the model means the model reasons over placeholders. Citations use alarm,
  anomaly and runbook ids, which are never redacted.
