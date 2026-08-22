#!/usr/bin/env bash
# Explicitly creates every Kafka topic used in SCHEMA.md. docker-compose.yml already sets
# KAFKA_AUTO_CREATE_TOPICS_ENABLE=true so this isn't strictly required for the app to
# work, but pre-creating them makes topic existence/partition count deliberate instead of
# an accident of whichever service happens to publish first.
set -euo pipefail

TOPICS=(
  documents.ingested
  documents.processed
  documents.reviewed
  vendor.onboarded
  vendor.updated
  procurement.request.created
  approval.requested
  approval.approved
  approval.rejected
  approval.escalated
  inventory.reserved
  inventory.backorder
  contract.generated
  contract.signed
  risk.assessed
)

for topic in "${TOPICS[@]}"; do
  echo "Ensuring Kafka topic: $topic"
  docker compose exec -T kafka kafka-topics --bootstrap-server localhost:9092 \
    --create --if-not-exists --topic "$topic" --partitions 3 --replication-factor 1
done
