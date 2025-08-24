#!/usr/bin/env sh
set -e

# Wait for DB (simple loop)
until python -c "import sys,psycopg2,os; psycopg2.connect(os.environ['DATABASE_URL'])" 2>/dev/null; do
  echo "⏳ Waiting for Postgres..."; sleep 2
done

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Start ASGI server (Channels-ready)
exec daphne -b 0.0.0.0 -p 8000 core.asgi:application
