.PHONY: up-core up-tools up-ui down topics test lint fmt smoke sim sim-loop sim-docker gateway console-install console console-build console-lint console-test test-all

up-core:
	docker compose --profile core up -d

up-tools:
	docker compose --profile core --profile tools up -d

up-ui:
	docker compose --profile core --profile ui up --build -d

down:
	docker compose --profile core --profile tools --profile ui --profile sim down

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
