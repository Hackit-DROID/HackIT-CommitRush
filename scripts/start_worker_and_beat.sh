#!/usr/bin/env bash
set -e

echo "=== Starting CommitRush Celery Worker + Beat (Embedded) ==="
CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"

exec celery -A commitrush worker \
    --workdir backend \
    -B \
    -l INFO \
    -c "${CONCURRENCY}" \
    -Q webhooks,sync,merge,validation,analytics,default \
    -s /tmp/celerybeat-schedule \
    -n "worker_beat@%h"
