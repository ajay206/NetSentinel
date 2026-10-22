# Risk register (W24)

NetSentinel is a portfolio / lab system on **synthetic data only**. This register covers the ML and LLM parts and how the pipeline controls them. Owner: Ajay Kumar Kondeti. Review it with every release tag.

| # | Risk | Likelihood | Impact | Control (where) | Residual |
|---|---|---|---|---|---|
| R1 | A degraded fault classifier gets deployed silently | Medium | High: wrong fault type steers triage | Eval gate re-scores every candidate on an independent hold-out (seed 9001) against floors and the champion; CI and `retrain.yml` block on failure (`evals/gate.py`, `evals/gate_thresholds.json`). The console shows the served version and gate result | Low |
| R2 | Tampered model artifact | Low | High | ML-DSA-65 signature checked in CI (`verify-model.yml`) and on load with `MODEL_VERIFY=enforce` (ml-service). The gate sidecar is kept outside the signed file set | Low |
| R3 | Data drift makes the model stale | Medium | Medium | Weekly `retrain.yml` and a PSI drift check per feature (warn above 0.1, drift above 0.2) | Medium: synthetic data only, so real drift isn't exercised |
| R4 | LLM prompt injection / data exfiltration through the copilot | Medium | High | llm-gateway injection guard, PII redaction, per-caller tokens and rate limits; red-team set (`evals/redteam.jsonl`); copilot actions need human approval (ticket-service) | Low–Medium |
| R5 | PII in traces / metrics | Low | Medium | Metrics use a fixed service label (no IDs or user input); the OTel collector drops PII attributes; Langfuse is self-hosted and opt-in | Low |
| R6 | Forged identity headers between services | Low | High | Internal tokens for ticket-service and incident-service (`X-NS-Internal-Token`); gateway JWT/RBAC | Low |
| R7 | Supply chain (base images, dependencies) | Medium | Medium | `uv.lock` / `package-lock.json` pinned; images built in CI to GHCR from tagged commits; Dependabot not enabled yet | Medium |
| R8 | Laptop resource exhaustion (8 GB) | High | Low | Memory limits on every container and pod; obs and k3d are opt-in | Low |
| R9 | Real customer / CSG data enters the repo | Low | High | Synthetic-only rule; data contract below; generators are deterministic (`libs/netgen`) | Low |

Open items: enable Dependabot / image scanning (R7); measure drift on a non-synthetic shadow feed (R3, out of scope).
