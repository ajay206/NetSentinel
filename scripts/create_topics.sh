#!/usr/bin/env bash
set -euo pipefail

echo "Creating Kafka topics (if not exist)..."
for t in alarms.raw alarms.enriched kpis incidents; do
  docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 --create --if-not-exists \
    --topic "$t" --partitions 3 --replication-factor 1 \
    --config retention.ms=604800000
done

echo "Current Kafka topics:"
docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --list
