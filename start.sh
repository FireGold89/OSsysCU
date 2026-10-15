#!/bin/sh
set -e

# GUNICORN_WORKERS：顯式設定優先；V2 試跑預設 2，其餘預設 1（SQLite 勿盲目加太多）
if [ -n "${GUNICORN_WORKERS:-}" ]; then
  WORKERS="$GUNICORN_WORKERS"
elif [ "${DEPLOYMENT_TIER:-}" = "v2" ]; then
  WORKERS=2
else
  WORKERS=1
fi
THREADS="${GUNICORN_THREADS:-4}"
TIMEOUT="${GUNICORN_TIMEOUT:-180}"

exec gunicorn \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers "$WORKERS" \
  --threads "$THREADS" \
  --timeout "$TIMEOUT" \
  wsgi:app
