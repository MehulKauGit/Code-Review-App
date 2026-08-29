#!/bin/sh
set -e

echo "=== [1/3] Applying Database Migrations ==="
alembic upgrade head || {
    echo "Warning: Database migration failed or database unreachable yet. Continuing startup..."
}

echo "=== [2/3] Starting Celery Background Worker ==="
celery -A workers.celery_app worker --loglevel=info --concurrency=2 -Q celery,parse,llm &
CELERY_PID=$!


# Trap signals for graceful shutdown of background worker
cleanup() {
    echo "Received termination signal. Shutting down gracefully..."
    kill -TERM "$CELERY_PID" 2>/dev/null || true
    wait "$CELERY_PID" 2>/dev/null || true
    exit 0
}
trap cleanup TERM INT


echo "=== [3/3] Starting FastAPI (Uvicorn) on port ${PORT:-8000} ==="
uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
UVICORN_PID=$!

wait "$UVICORN_PID"
