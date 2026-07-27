#!/bin/sh
set -e

alembic upgrade head

# On platforms with only one free process slot (e.g. Render's free Web
# Service tier), RUN_WORKER_INLINE=true runs the Celery worker/beat inside
# this same container instead of as a separate service. docker-compose
# already runs a dedicated `worker` service, so it leaves this unset to
# avoid running two consumers against the same queues.
if [ "$RUN_WORKER_INLINE" = "true" ]; then
    celery -A app.worker worker --beat --loglevel=info -Q celery,notifications &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
