#!/usr/bin/env bash
set -e

echo "=== Starting CommitRush Celery Worker ==="
CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"

exec celery -A commitrush worker \
    --workdir backend \
    -l INFO \
    -c "${CONCURRENCY}" \
    -Q webhooks,sync,merge,validation,analytics,default \
    -n "worker@%h"
