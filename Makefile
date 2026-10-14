.PHONY: up-core up-tools down topics test lint fmt smoke

up-core:
	docker compose --profile core up -d

up-tools:
	docker compose --profile core --profile tools up -d

down:
	docker compose --profile core --profile tools down

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
