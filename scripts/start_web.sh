#!/usr/bin/env bash
set -e

echo "=== Starting CommitRush Web Service ==="
python backend/manage.py migrate --noinput
python backend/manage.py collectstatic --noinput

PORT="${PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-3}"

echo "Starting Gunicorn on port ${PORT} with ${WEB_CONCURRENCY} workers..."
exec gunicorn commitrush.wsgi:application \
    --chdir backend \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WEB_CONCURRENCY}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
