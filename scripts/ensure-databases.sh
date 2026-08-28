#!/usr/bin/env bash
# Idempotently create every per-service database.
#
# Why this exists separately from infra/postgres/init-multiple-dbs.sh: that script is
# mounted into /docker-entrypoint-initdb.d/, and Postgres only runs those scripts when the
# data directory is *empty* — i.e. exactly once, when the volume is first created. Adding a
# new service later (notification_agent added medisource_notifications) therefore does NOT
# create its database on any environment whose volume already existed, and the new service
# crashes on startup with:
#
#   FATAL:  database "medisource_notifications" does not exist
#
# which reads like a broken service rather than stale volume state. This script re-asserts
# the full database list on every deploy, so adding a service to DATABASES is enough and no
# one has to know to wipe their volume.
set -euo pipefail
cd "$(dirname "$0")/.."

POSTGRES_USER="${POSTGRES_USER:-medisource}"

DATABASES="medisource_documents medisource_vendors medisource_approvals medisource_inventory medisource_contracts medisource_risk medisource_notifications"

for db in $DATABASES; do
  # Postgres has no CREATE DATABASE IF NOT EXISTS; \gexec runs the generated statement
  # only when the SELECT returns a row, making this a no-op for databases that exist.
  exists=$(docker compose exec -T postgres \
    psql -U "$POSTGRES_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='$db'" 2>/dev/null || true)
  if [ "$exists" = "1" ]; then
    echo "  $db already exists"
  else
    echo "  creating $db"
    docker compose exec -T postgres \
      psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $db" >/dev/null
  fi
done
