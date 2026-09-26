#!/usr/bin/env bash
set -e

echo "=== Starting CommitRush Celery Beat Scheduler ==="
exec celery -A commitrush beat \
    --workdir backend \
    -l INFO \
    --pidfile= \
    -s /tmp/celerybeat-schedule
