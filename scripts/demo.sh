#!/usr/bin/env bash
# W12 one-command Phase 1 demo: stack up -> topics -> KPI backfill -> fibre_cut -> smoke.
# Synthetic data only. Needs Docker; Ollama on the host is optional (else fallback answers).
set -euo pipefail
cd "$(dirname "$0")/.."

PROFILES=(--profile core --profile ui --profile pipeline --profile rag --profile copilot --profile ops)
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8000}"
WAIT_S="${DEMO_WAIT_S:-240}"

step() { printf '\n==> %s\n' "$*"; }

step "Starting the Phase 1 stack (core, ui, pipeline, rag, copilot)"
docker compose "${PROFILES[@]}" up -d --build

step "Creating Kafka topics"
bash scripts/create_topics.sh

step "Waiting up to ${WAIT_S}s for the gateway to be ready"
deadline=$((SECONDS + WAIT_S))
until curl -sf "${GATEWAY_URL}/readyz" >/dev/null; do
  if (( SECONDS > deadline )); then
    echo "gateway not ready after ${WAIT_S}s; see: docker compose logs api-gateway" >&2
    exit 1
  fi
  sleep 3
done

step "Back-filling 1 day of KPIs (seed 42)"
uv run netgen-sim kpis --seed 42 --days 1

step "Running the fibre_cut scenario (seed 42, 60x)"
uv run netgen-sim run --seed 42 --scenario fibre_cut --speed 60x

step "Smoke test through the gateway"
bash scripts/smoke.sh --base-url "${GATEWAY_URL}" --wait 120

cat <<MSG

Demo ready. Open the console:
  make console      # then http://localhost:5173 (sign in as operator / operator)
Follow the "Demo path" strip: alarms -> KPI anomaly -> fault badge -> runbooks -> copilot.
MSG
