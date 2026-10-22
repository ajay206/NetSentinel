#!/usr/bin/env bash
# W23: headless Locust run + copilot replica sampling -> loadtest/report.md
set -euo pipefail
HOST=${LOAD_HOST:-http://localhost:8080}
USERS=${LOAD_USERS:-20}
DURATION=${LOAD_DURATION:-3m}
OUT=$(mktemp -d)
: > "$OUT/replicas.log"
( while true; do kubectl get deploy copilot-orchestrator -o jsonpath='{.status.replicas}' >> "$OUT/replicas.log" 2>/dev/null || true; echo >> "$OUT/replicas.log"; sleep 10; done ) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null || true' EXIT
uvx --from locust locust -f loadtest/locustfile.py --host "$HOST" --headless \
  -u "$USERS" -r 2 -t "$DURATION" --csv "$OUT/locust" --only-summary || true
python3 loadtest/report.py "$OUT/locust" "$OUT/replicas.log" loadtest/report.md
