.PHONY: logs ps reset-db tools-build incidents up-core up-tools up-ui down topics test lint fmt smoke sim sim-loop sim-docker gateway console-install console console-build console-lint console-test test-all ingest up-pipeline enriched-peek ingest-stats kpi-service kpi-stats kpi-query ml ml-train anomalies topology kpis kpis-follow kpis-peek docs-check ml-train-xgb up-rag rag rag-ingest rag-eval runbooks copilot up-copilot analyze ollama-pull mcp mcp-dev mcp-contract copilot-contract gateway-contract token demo kafka-smoke incident up-incident incidents-peek incident-eval up-graph topo-load impact topology-contract rag-bench rag-bench-dev up-tickets ticket-migrate ticket-contract tickets agents agent-runs llm-gateway-contract llm-gateway-redteam pqc-init pqc-probe pqc-bench pqc-tamper pqc-verify up-obs down-obs obs-check k3d-up k3d-images k3d-install k3d-status k3d-load k3d-down helm-lint

# Targets marked (dev) run on the host and need uv / Node; everything else needs only Docker.

up-core:
	docker compose --profile core up -d

up-tools:
	docker compose --profile core --profile tools up -d

up-ui:
	docker compose --profile core --profile ui up --build -d

# Every compose profile: `docker compose logs/ps/down` only see services whose profile is enabled
PROFILES := --profile core --profile tools --profile ui --profile sim --profile pipeline --profile rag --profile copilot --profile ops --profile graph --profile cli --profile obs
# One-shot tools container (netgen-sim, smoke.py, gw.py) on the compose network
TOOLS := docker compose --profile cli run --rm --no-deps -T tools

# W22 observability (opt-in, ~0.9 GB): Prometheus :9090, Grafana :3000, Langfuse :3001,
# MLflow :5000, OTel collector :4317/:4318. Run after `make demo` / `make up-ui`.
up-obs:
	docker compose --profile core --profile ui --profile obs up -d otel-collector prometheus grafana langfuse-db-init langfuse mlflow

down-obs:
	docker compose --profile obs stop otel-collector prometheus grafana langfuse mlflow

obs-check:
	python3 scripts/obs_check.py

# W23 local Kubernetes (opt-in). Stop compose first on 8 GB: `make down`.
K3D_IMAGES := api-gateway alarm-ingest kpi-service ml-service incident-service copilot-orchestrator netgen-simulator noc-console
k3d-up:
	k3d cluster create --config deploy/k3d/cluster.yaml

k3d-images:
	COMPOSE_PROJECT_NAME=netsentinel docker compose --profile ui --profile pipeline --profile ops --profile copilot --profile sim build $(K3D_IMAGES)
	for s in $(K3D_IMAGES); do docker tag netsentinel-$$s netsentinel-$$s:local; done
	k3d image import -c netsentinel $(addprefix netsentinel-,$(addsuffix :local,$(K3D_IMAGES)))

k3d-install:
	helm upgrade --install ns deploy/helm/netsentinel -f deploy/helm/values-local.yaml --wait --timeout 10m

k3d-status:
	kubectl get pods,svc,hpa,ingress

k3d-load:
	bash loadtest/run.sh

k3d-down:
	k3d cluster delete netsentinel

helm-lint:
	helm lint deploy/helm/netsentinel -f deploy/helm/values-local.yaml

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

# Step 15: vector vs bm25 vs hybrid vs rerank vs Graph RAG -> evals/retrieval_report.md
rag-bench:
	docker compose --profile rag build rag-service
	docker compose --profile rag run --rm --no-deps -e GRAPH_CONTEXT=local \
		-v "$(CURDIR)/evals:/app/evals" --user "$$(id -u):$$(id -g)" rag-service \
		python -m rag_service.bench --modes vector,bm25,hybrid,rerank,graph \
		--out evals/retrieval_report.md

# (dev) needs uv/Node on the host
rag-bench-dev:
	uv run python -m rag_service.bench --modes vector,hybrid,graph --out evals/retrieval_report.md

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

llm-gateway-contract:
	uv run python scripts/gen_llm_gateway_contract.py

llm-gateway-redteam:
	uv run pytest services/llm-gateway -k redteam

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

# Step 17: one multi-agent run on a seeded fibre-cut site (needs `make demo` + TOKEN=operator JWT);
# it stops at the human approval node: approve it in the console (Copilot chat)
SITE ?= SITE-010
agents:
	curl -s -XPOST localhost:8000/api/copilot/runs -H "Authorization: Bearer $(TOKEN)" \
		-H 'content-type: application/json' -d '{"siteId":"$(SITE)"}'; echo

agent-runs:
	curl -s -H "Authorization: Bearer $(TOKEN)" localhost:8000/api/copilot/runs; echo

# Step 16: ticket-service (drafts + approvals + audit) on TimescaleDB
up-tickets:
	docker compose --profile ops up -d --build timescaledb ticket-service

# `alembic upgrade head` inside the container (also runs on every start)
ticket-migrate:
	docker compose --profile ops exec -T ticket-service alembic upgrade head

ticket-contract:
	uv run python scripts/gen_ticket_contract.py

# Approval queue via the gateway (needs TOKEN, e.g. TOKEN=$$(make -s token))
tickets:
	curl -s -H "Authorization: Bearer $(TOKEN)" localhost:8000/api/tickets; echo

# Step 14: Neo4j knowledge graph + topology-service (~1 GB RAM)
up-graph:
	docker compose --profile graph up -d --build neo4j topology-service

# Re-load topology + runbooks into Neo4j (idempotent MERGE); runs inside the container
topo-load:
	docker compose --profile graph exec -T topology-service topology-load

LINK ?= LNK-012
impact:
	@$(TOOLS) python scripts/gw.py call GET "/api/graph/impact?linkId=$(LINK)" --as viewer

# Step 21: post-quantum (Docker only; the pqc-init image has OpenSSL 3.5 + ns-pqc)
pqc-init:
	docker compose --profile copilot run --rm pqc-init

pqc-probe:
	docker compose --profile copilot run --rm --no-deps pqc-init python -c "import json,ns_pqc;print(json.dumps(ns_pqc.probe_tls('llm-gateway',8443,'/pqc/ca.crt'),indent=1))"

pqc-bench:
	docker compose --profile copilot run --rm --no-deps pqc-init python scripts/bench_tls.py --rounds 1000

pqc-verify:
	docker compose exec ml-service python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8003/model/signature').read().decode())"

# Demo: alter the served model; after the restart ml-service refuses it (MODEL_VERIFY=enforce)
pqc-tamper:
	docker compose exec ml-service sh -c 'echo " " >> $$(ls -d /tmp/models/fault_classifier/*/ | head -1)meta.json'
	docker compose restart ml-service

