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

# Nginx resolves each upstream hostname once, at worker start, and caches the address.
# `docker compose up` hands the service containers new IPs, so a gateway that was already
# running is left pointing at addresses that now belong to different containers — requests
# then land on the wrong service and come back 404, which looks like a broken deploy or a
# missing route. Restarting the gateway after the services settle makes it re-resolve.
echo "Restarting the gateway so it picks up the new service addresses..."
docker compose restart gateway >/dev/null 2>&1 || true

# The seed talks to the services through the gateway, so wait for it to actually answer
# rather than assuming a fixed sleep was long enough.
for _ in $(seq 1 30); do
  if curl -sf -m 5 http://localhost/api/health/vendors >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Loading demo seed data..."
if command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --quiet requests reportlab 2>/dev/null || true
  python3 scripts/seed-data.py
else
  echo "python3 not found on host — skipping seed data. Run 'python scripts/seed-data.py' manually once Python is available."
fi

# DocuSign is integrated into contract_intelligence; it is not a separate container.
# Authenticate against the configured Demo account and probe the public webhook URL so
# the deploy output distinguishes a running stack from a usable signing integration.
echo "Checking DocuSign authentication and Connect callback..."
if docker compose exec -T contract_intelligence python - <<'PY'
import sys
import requests
from app.config import settings
from app.esign_client import (
    _access_token,
    _account_and_base_url,
    connect_configured,
    credentials_configured,
)

if not credentials_configured():
    print("DocuSign is not ready: integration key, user ID, or RSA private key is missing/invalid.")
    sys.exit(1)
if not connect_configured():
    print("DocuSign is not ready: public HTTPS Connect URL or HMAC key is missing.")
    sys.exit(1)

try:
    _access_token()
    _account_and_base_url()
except Exception as exc:
    print(f"DocuSign API authentication/account check failed: {exc}")
    sys.exit(1)

try:
    response = requests.get(
        settings.docusign_connect_url.strip(),
        headers={"ngrok-skip-browser-warning": "1"},
        timeout=12,
    )
except requests.RequestException as exc:
    print(f"DocuSign Connect callback is unreachable: {exc}")
    sys.exit(1)

if response.status_code != 405:
    print(
        "DocuSign Connect callback probe returned HTTP "
        f"{response.status_code}; expected 405 from the POST-only webhook route."
    )
    sys.exit(1)

print("DocuSign JWT authentication and account access: OK")
print("DocuSign Connect HTTPS callback is reachable: OK")
PY
then
  echo "  DocuSign signing integration is ready for a real envelope test."
else
  echo "  WARNING: the app stack is running, but DocuSign readiness failed. Check the message above, DocuSign consent, the active ngrok tunnel, and the Connect HMAC configuration."
fi

echo ""
echo "MediSource AI is up:"
echo "  App:          http://localhost"
echo "  Temporal UI:  http://localhost:8088"
echo "  MLflow UI:    http://localhost:5000"
echo "  MinIO console:http://localhost:9001"
echo "  OPA:          http://localhost:8181"
