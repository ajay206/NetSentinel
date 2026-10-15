.PHONY: logs ps reset-db tools-build incidents up-core up-tools up-ui down topics test lint fmt smoke sim sim-loop sim-docker gateway console-install console console-build console-lint console-test test-all ingest up-pipeline enriched-peek ingest-stats kpi-service kpi-stats kpi-query ml ml-train anomalies topology kpis kpis-follow kpis-peek docs-check ml-train-xgb up-rag rag rag-ingest rag-eval runbooks copilot up-copilot analyze ollama-pull mcp mcp-dev mcp-contract copilot-contract gateway-contract token demo kafka-smoke incident up-incident incidents-peek incident-eval up-graph topo-load impact topology-contract

# Targets marked (dev) run on the host and need uv / Node; everything else needs only Docker.

up-core:
	docker compose --profile core up -d

up-tools:
	docker compose --profile core --profile tools up -d

up-ui:
	docker compose --profile core --profile ui up --build -d

# Every compose profile: `docker compose logs/ps/down` only see services whose profile is enabled
PROFILES := --profile core --profile tools --profile ui --profile sim --profile pipeline --profile rag --profile copilot --profile ops --profile graph --profile cli
# One-shot tools container (netgen-sim, smoke.py, gw.py) on the compose network
TOOLS := docker compose --profile cli run --rm --no-deps -T tools

down:
	docker compose $(PROFILES) down

# make logs S=kpi-service [F=1 to follow]
S ?=
logs:
	docker compose $(PROFILES) logs --tail=200 $(if $(F),-f) $(S)

ps:
	docker compose $(PROFILES) ps

# Removes the TimescaleDB volume (all KPI data). Needed when pg-data was initialised with a
# different POSTGRES_PASSWORD than the one in .env (Postgres only reads it on first init).
reset-db:
	docker compose $(PROFILES) rm -sf timescaledb kpi-service ml-service
	-docker volume rm netsentinel_pg-data
	@echo "pg-data removed; start again with: make demo (or make up-pipeline)"

topics:
	bash scripts/create_topics.sh

# (dev) needs uv/Node on the host
test:
	uv run pytest

# (dev) needs uv/Node on the host
lint:
	uv run ruff check .

# (dev) needs uv/Node on the host
fmt:
	uv run ruff format .

# W12: Phase 1 end-to-end demo and smoke test (gateway must be running)
demo:
	bash scripts/demo.sh

smoke:
	bash scripts/smoke.sh

tools-build:
	docker compose --profile cli build tools

kafka-smoke:
	@echo '{"smoke": "test", "siteId": "SITE-001"}' | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic alarms.raw
	@echo "Consumed test message:"
	docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic alarms.raw --from-beginning --max-messages 1 --timeout-ms 5000

sim:
	$(TOOLS) netgen-sim run --seed 42 --scenario fibre_cut --speed 60x

sim-loop:
	$(TOOLS) netgen-sim run --seed 42 --scenario fibre_cut --speed 60x --loop

sim-docker:
	docker compose --profile core --profile sim up -d --build netgen-simulator

# (dev) needs uv/Node on the host
gateway:
	uv run uvicorn api_gateway.main:app --reload --port 8000

console-install:
	npm --prefix apps/noc-console ci

# (dev) needs uv/Node on the host
console:
	npm --prefix apps/noc-console run dev

console-build:
	npm --prefix apps/noc-console run build

console-lint:
	npm --prefix apps/noc-console run lint
	npm --prefix apps/noc-console run typecheck

console-test:
	npm --prefix apps/noc-console run test

test-all: test console-test

# (dev) needs uv/Node on the host
topology:
	uv run netgen topology --seed 42 --out data/topology.json

kpis:
	$(TOOLS) netgen-sim kpis --seed 42 --days 1

kpis-follow:
	$(TOOLS) netgen-sim kpis --seed 42 --days 1 --follow

kpis-peek:
	docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic kpis --from-beginning --max-messages 5 --timeout-ms 10000

# (dev) needs uv/Node on the host
ingest:
	uv run uvicorn alarm_ingest.main:app --port 8001

up-pipeline:
	docker compose --profile core --profile pipeline up -d --build

ingest-stats:
	curl -s localhost:8001/stats; echo

enriched-peek:
	docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic alarms.enriched --from-beginning --max-messages 5 --timeout-ms 10000

# (dev) needs uv/Node on the host
kpi-service:
	uv run --env-file .env uvicorn kpi_service.main:app --port 8002

kpi-stats:
	curl -s localhost:8002/stats; echo

kpi-query:
	curl -s "localhost:8000/api/kpi/cells?limit=3"; echo

# (dev) needs uv/Node on the host
ml:
	uv run uvicorn ml_service.api:app --port 8003

# (dev) needs uv/Node on the host
ml-train:
	uv run python -m ml_service.train_baselines --experiment anomaly-baselines --seed 42 --days 7

# (dev) needs uv/Node on the host
ml-train-xgb:
	cd services/ml-service && uv run python -m ml_service.train_xgb --register

up-rag:
	docker compose --profile rag up -d --build qdrant rag-service

# (dev) needs uv/Node on the host
rag:
	uv run uvicorn rag_service.api:app --port 8004

# (dev) needs uv/Node on the host
runbooks:
	python3 scripts/gen_runbooks.py

# (dev) needs uv/Node on the host
rag-ingest:
	uv run python -m rag_service.ingest data/runbooks

# (dev) needs uv/Node on the host
rag-eval:
	uv run python -m rag_service.eval --mode all --k 3

# (dev) needs uv/Node on the host
copilot:
	uv run uvicorn copilot_orchestrator.api:app --port 8005

up-copilot:
	docker compose --profile copilot up -d --build mcp-server copilot-orchestrator

# (dev) needs uv/Node on the host
mcp:
	MCP_ALLOW_NO_TOKEN=1 uv run uvicorn --factory mcp_server.app:build_app --port 8006

# (dev) needs uv/Node on the host
mcp-dev:
	uv run mcp dev services/mcp-server/src/mcp_server/server.py

mcp-contract:
	uv run python scripts/gen_mcp_contract.py

copilot-contract:
	uv run python scripts/gen_copilot_contract.py

gateway-contract:
	uv run python scripts/gen_gateway_auth_contract.py

topology-contract:
	uv run python scripts/gen_topology_contract.py

# W11: get a JWT from the gateway (demo users; synthetic data only)
AS ?= operator
token:
	@$(TOOLS) python scripts/gw.py token --as $(AS)

ollama-pull:
	ollama pull qwen2.5:1.5b

SITE ?= SITE-012
WINDOW ?= 30m
analyze:
	@$(TOOLS) python scripts/gw.py call POST /api/copilot/analyze --as operator --data '{"siteId":"$(SITE)","window":"$(WINDOW)"}'

anomalies:
	@$(TOOLS) python scripts/gw.py call GET "/api/ml/anomalies?hours=24&limit=5" --as viewer

incidents:
	@$(TOOLS) python scripts/gw.py call GET "/api/incidents?limit=5" --as viewer

# (dev) needs uv/Node on the host
docs-check:
	python3 scripts/check_docs.py

# (dev) needs uv/Node on the host
incident:
	DISABLE_KAFKA=0 uv run uvicorn incident_service.main:app --port 8007

up-incident:
	docker compose --profile core --profile pipeline --profile ops up -d --build incident-service

incidents-peek:
	docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic incidents --from-beginning --property print.key=true --max-messages 5 --timeout-ms 10000

# (dev) needs uv/Node on the host
incident-eval:
	uv run incident-eval --out evals/rca_report.md

# Step 14: Neo4j knowledge graph + topology-service (~1 GB RAM)
up-graph:
	docker compose --profile graph up -d --build neo4j topology-service

# Re-load topology + runbooks into Neo4j (idempotent MERGE); runs inside the container
topo-load:
	docker compose --profile graph exec -T topology-service topology-load

LINK ?= LNK-012
impact:
	@$(TOOLS) python scripts/gw.py call GET "/api/graph/impact?linkId=$(LINK)" --as viewer
