#!/bin/sh
# PATHS backend container entrypoint.
#
# Makes `docker compose up` turnkey: it applies the database schema with Alembic
# (retrying while Postgres finishes coming up) and then launches the API server.
# Disable the migration step by setting RUN_MIGRATIONS=0.
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
  attempt=0
  until alembic upgrade head; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 10 ]; then
      echo "[entrypoint] Migrations still failing after ${attempt} attempts — aborting." >&2
      exit 1
    fi
    echo "[entrypoint] Database not ready (attempt ${attempt}/10) — retrying in 3s..."
    sleep 3
  done
  echo "[entrypoint] Migrations applied."
fi

echo "[entrypoint] Starting Uvicorn on 0.0.0.0:${APP_PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}"
