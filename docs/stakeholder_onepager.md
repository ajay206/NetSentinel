# NetSentinel: stakeholder one-pager

**What:** an AI copilot for telecom NOC teams. It ingests alarms and KPIs, groups alarms into incidents, explains the likely fault (XGBoost + SHAP), finds the right runbook (RAG / Graph RAG), and drafts a ticket that a human must approve.

**Why it matters:** NOC engineers lose time correlating alarm storms and searching runbooks. NetSentinel does the correlation and evidence gathering, and the engineer stays in charge.

**Safety by design**
- Synthetic data only. Every LLM call goes through one gateway, which applies an injection guard, PII redaction and rate limits.
- Tickets and agent plans need human approval, with an audit trail.
- Models ship only after an eval gate, are ML-DSA signed, and have their version shown in the console (no silent swaps).
- Post-quantum hybrid TLS is used for copilot-to-LLM traffic.

**How it runs:** `make demo` on an 8 GB laptop (Docker). Opt-in extras: observability (`make up-obs`) and local Kubernetes (`make k3d-up k3d-images k3d-install`).

**Quality gates in CI:** lint, about 620 Python and 190 console tests, a responsive layout audit, an eval gate with a degraded-model self-test, a drift check, signature verification, Helm validation and image builds to GHCR.

**Status:** Phases 1 and 2 are complete. Production hardening (W22–W24) is built. Next: TelcoGPT-mini (a small telecom-tuned model, Phase 3) and cloud providers (W25), both pending Ajay's go-ahead.

**Contact:** Ajay Kumar Kondeti (github.com/ajay206).
