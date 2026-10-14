#!/usr/bin/env bash
# W12 Phase 1 smoke test through the gateway (synthetic data only).
# Runs inside the tools container (host needs only Docker), against http://api-gateway:8000.
# Usage: bash scripts/smoke.sh [--user operator] [--wait 120] [--json]
# Set SMOKE_LOCAL=1 to run on the host with uv instead (dev; uses GATEWAY_URL or localhost).
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${SMOKE_LOCAL:-0}" == "1" ]]; then
  exec uv run python scripts/smoke.py "$@"
fi
exec docker compose --profile cli run --rm --no-deps -T tools python scripts/smoke.py "$@"
