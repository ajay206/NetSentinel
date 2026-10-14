#!/usr/bin/env bash
# W12 one-command Phase 1 demo: stack up -> topics -> KPI backfill -> fibre_cut -> smoke.
# Host prerequisites: Docker (Compose v2), make, git. Everything else runs in containers.
# Synthetic data only. Ollama on the host is optional (else deterministic fallback answers).
set -euo pipefail
cd "$(dirname "$0")/.."

PROFILES=(--profile core --profile ui --profile pipeline --profile rag --profile copilot --profile ops)
WAIT_S="${DEMO_WAIT_S:-240}"
# One-shot tools container on the compose network (netgen-sim, smoke.py, gw.py)
TOOLS=(docker compose --profile cli run --rm --no-deps -T tools)

step() { printf '\n==> %s\n' "$*"; }

if [[ ! -f .env ]]; then
  step "No .env found: creating one from env.example.txt (dev-only values)"
  cp env.example.txt .env
fi

step "Building images (first run takes a few minutes)"
docker compose "${PROFILES[@]}" --profile cli build

step "Starting the Phase 1 stack (core, ui, pipeline, rag, copilot, ops)"
docker compose "${PROFILES[@]}" up -d

step "Creating Kafka topics"
bash scripts/create_topics.sh

step "Waiting up to ${WAIT_S}s for the gateway to be ready"
"${TOOLS[@]}" python scripts/gw.py wait --timeout "${WAIT_S}"

step "Back-filling 1 day of KPIs (seed 42)"
"${TOOLS[@]}" netgen-sim kpis --seed 42 --days 1

step "Running the fibre_cut scenario (seed 42, 60x)"
"${TOOLS[@]}" netgen-sim run --seed 42 --scenario fibre_cut --speed 60x

step "Smoke test through the gateway"
"${TOOLS[@]}" python scripts/smoke.py --wait 120

cat <<MSG

Demo ready. Dashboard (noc-console container): http://localhost:5173 (sign in as operator / operator)
Follow the "Demo path" strip: alarms -> KPI anomaly -> fault badge -> runbooks -> copilot.
Logs: make logs S=<service>    Stop: make down
MSG
