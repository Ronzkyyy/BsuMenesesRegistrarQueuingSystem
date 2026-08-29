#!/bin/sh
set -e

alembic upgrade head

# Idempotent: seed_initial_data() no-ops if any queue already exists, so this
# is safe to run on every boot rather than requiring a one-off manual step.
python -m app.core.init_db

# On platforms with only one free process slot (e.g. Render's free Web
# Service tier), RUN_WORKER_INLINE=true runs the Celery worker/beat inside
# this same container instead of as a separate service. docker-compose
# already runs a dedicated `worker` service, so it leaves this unset to
# avoid running two consumers against the same queues.
if [ "$RUN_WORKER_INLINE" = "true" ]; then
    celery -A app.worker worker --beat --loglevel=info -Q celery,notifications &
fi

# --proxy-headers + --forwarded-allow-ips="*": trust X-Forwarded-Proto/For
# from the TLS-terminating proxy in front of this container (the platform
# load balancer / nginx) so request.url.scheme is "https" in production and
# the HTTPS-only response headers actually fire. Safe because this container
# is never published directly - it's only reachable through that proxy.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
    --proxy-headers --forwarded-allow-ips="*"
