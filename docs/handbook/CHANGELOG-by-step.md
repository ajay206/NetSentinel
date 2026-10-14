# Changelog by Step

## Step 1: Week 1 Bootstrap & Core Infrastructure
* **Date:** 2026-10-14
* **Scope:** Monorepo skeleton, `uv` workspace root, `ns-common` shared library, Docker Compose (`core` and `tools` profiles with Kafka KRaft and TimescaleDB), idempotent topic creation script (`scripts/create_topics.sh`), Makefile automation targets, ADRs, and junior developer handover guide under `docs/handbook/`.
* **Verification:**
  - `uv workspace` initialized successfully.
  - `ns-common` smoke tests passing.
  - CI pipeline and pre-commit configured.
