.PHONY: up-core up-tools up-ui down topics test lint fmt smoke sim sim-loop sim-docker gateway console-install console console-build console-lint console-test test-all ingest up-pipeline enriched-peek ingest-stats kpi-service kpi-stats kpi-query ml ml-train anomalies topology kpis kpis-follow kpis-peek docs-check ml-train-xgb up-rag rag rag-ingest rag-eval runbooks copilot up-copilot analyze ollama-pull mcp mcp-dev mcp-contract copilot-contract

up-core:
	docker compose --profile core up -d

up-tools:
	docker compose --profile core --profile tools up -d

up-ui:
	docker compose --profile core --profile ui up --build -d

down:
	docker compose --profile core --profile tools --profile ui --profile sim --profile pipeline down

topics:
	bash scripts/create_topics.sh

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

smoke:
	@echo '{"smoke": "test", "siteId": "SITE-001"}' | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic alarms.raw
	@echo "Consumed test message:"
	docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic alarms.raw --from-beginning --max-messages 1 --timeout-ms 5000

sim:
	uv run netgen-sim run --seed 42 --scenario fibre_cut --speed 60x

sim-loop:
	uv run netgen-sim run --seed 42 --scenario fibre_cut --speed 60x --loop

sim-docker:
	docker compose --profile core --profile sim up -d --build netgen-simulator

gateway:
	uv run uvicorn api_gateway.main:app --reload --port 8000

console-install:
	npm --prefix apps/noc-console ci

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

topology:
	uv run netgen topology --seed 42 --out data/topology.json

kpis:
	uv run netgen-sim kpis --seed 42 --days 1

kpis-follow:
	uv run netgen-sim kpis --seed 42 --days 1 --follow

kpis-peek:
	kcat -C -b localhost:9092 -t kpis -c 5 -e

ingest:
	uv run uvicorn alarm_ingest.main:app --port 8001

up-pipeline:
	docker compose --profile core --profile pipeline up -d --build

ingest-stats:
	curl -s localhost:8001/stats; echo

enriched-peek:
	docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic alarms.enriched --from-beginning --max-messages 5 --timeout-ms 10000

kpi-service:
	uv run --env-file .env uvicorn kpi_service.main:app --port 8002

kpi-stats:
	curl -s localhost:8002/stats; echo

kpi-query:
	curl -s "localhost:8000/api/kpi/cells?limit=3"; echo

ml:
	uv run uvicorn ml_service.api:app --port 8003

ml-train:
	uv run python -m ml_service.train_baselines --experiment anomaly-baselines --seed 42 --days 7

ml-train-xgb:
	cd services/ml-service && uv run python -m ml_service.train_xgb --register

up-rag:
	docker compose --profile rag up -d --build qdrant rag-service

rag:
	uv run uvicorn rag_service.api:app --port 8004

runbooks:
	python3 scripts/gen_runbooks.py

rag-ingest:
	uv run python -m rag_service.ingest data/runbooks

rag-eval:
	uv run python -m rag_service.eval --mode all --k 3

copilot:
	uv run uvicorn copilot_orchestrator.api:app --port 8005

up-copilot:
	docker compose --profile copilot up -d --build mcp-server copilot-orchestrator

mcp:
	MCP_ALLOW_NO_TOKEN=1 uv run uvicorn --factory mcp_server.app:build_app --port 8006

mcp-dev:
	uv run mcp dev services/mcp-server/src/mcp_server/server.py

mcp-contract:
	uv run python scripts/gen_mcp_contract.py

copilot-contract:
	uv run python scripts/gen_copilot_contract.py

ollama-pull:
	ollama pull qwen2.5:1.5b

SITE ?= SITE-012
WINDOW ?= 30m
analyze:
	curl -s -XPOST localhost:8000/api/copilot/analyze -H 'content-type: application/json' \
		-d '{"site_id":"$(SITE)","window":"$(WINDOW)"}'; echo

anomalies:
	curl -s "localhost:8000/api/ml/anomalies?hours=24&limit=5"; echo

docs-check:
	python3 scripts/check_docs.py
