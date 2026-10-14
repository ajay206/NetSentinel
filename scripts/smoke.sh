#!/usr/bin/env bash
# W12 Phase 1 smoke test through the gateway (synthetic data only).
# Usage: bash scripts/smoke.sh [--base-url URL] [--user operator] [--wait 120] [--json]
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python scripts/smoke.py "$@"
