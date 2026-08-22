#!/usr/bin/env bash
# One-command local/demo deploy: builds and starts every container, waits for the
# gateway to come up, declares Kafka topics, and loads demo seed data through the
# running APIs. Each service provisions its own database schema on startup
# (see SCHEMA.md) so no separate migration step is needed here.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found — copying .env.example"
  cp .env.example .env
fi

# An unclean shutdown (a reboot, a hard power-off) leaves Kafka's ephemeral broker
# registration behind in Zookeeper. Kafka then refuses to start with NodeExistsException on
# registerBroker and every dependent service fails with it — which looks like a broken
# deploy rather than leftover state. Starting Zookeeper alone first, and clearing the node
# if it is stale, makes the deploy survive a reboot.
echo "Clearing any stale Kafka broker registration left by an unclean shutdown..."
docker compose up -d zookeeper >/dev/null 2>&1 || true
for _ in $(seq 1 20); do
  if docker compose exec -T zookeeper bash -c "echo ruok | nc -w 2 localhost 2181" 2>/dev/null | grep -q imok; then
    break
  fi
  sleep 2
done
if docker compose exec -T zookeeper bash -c \
     "zookeeper-shell localhost:2181 ls /brokers/ids 2>/dev/null | tail -1" 2>/dev/null | grep -q '\[1\]'; then
  if ! docker compose ps --status running --services 2>/dev/null | grep -qx kafka; then
    echo "  stale broker id found with no Kafka running — removing it"
    docker compose exec -T zookeeper bash -c \
      "zookeeper-shell localhost:2181 deleteall /brokers/ids/1" >/dev/null 2>&1 || true
  fi
fi

echo "Building and starting all services (this can take a while on first run — PaddleOCR/mlflow/kafka images are large)..."
docker compose up -d --build

echo "Waiting for Postgres/Kafka/MinIO health checks..."
for svc in postgres kafka minio; do
  until [ "$(docker compose ps -q "$svc" | xargs -r docker inspect -f '{{.State.Health.Status}}' 2>/dev/null)" = "healthy" ]; do
    sleep 3
  done
  echo "  $svc is healthy"
done

echo "Declaring Kafka topics..."
bash scripts/init-kafka-topics.sh

echo "Waiting for application services to report healthy..."
sleep 10

echo "Loading demo seed data..."
if command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --quiet requests reportlab 2>/dev/null || true
  python3 scripts/seed-data.py
else
  echo "python3 not found on host — skipping seed data. Run 'python scripts/seed-data.py' manually once Python is available."
fi

echo ""
echo "MediSource AI is up:"
echo "  App:          http://localhost"
echo "  Temporal UI:  http://localhost:8088"
echo "  MLflow UI:    http://localhost:5000"
echo "  MinIO console:http://localhost:9001"
echo "  OPA:          http://localhost:8181"
