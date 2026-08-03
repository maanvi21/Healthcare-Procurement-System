#!/usr/bin/env bash
# Runs automatically on first Postgres container start (mounted into
# /docker-entrypoint-initdb.d/). Creates one database per microservice so each
# service owns its own schema (database-per-service pattern) on a single shared
# Postgres instance for local/demo deployment.
set -euo pipefail

DATABASES="medisource_documents medisource_vendors medisource_approvals medisource_inventory medisource_contracts medisource_risk"

for db in $DATABASES; do
  echo "Creating database: $db"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE $db OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done
