#!/bin/bash
set -e

echo "🚀 Starting ZamIO Django Application..."

# Wait for DB with timeout
echo "⏳ Waiting for database connection..."
timeout=60
counter=0
until python -c "
import os, psycopg2, sys
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    print('✅ Database connected successfully')
    sys.exit(0)
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
" 2>/dev/null; do
    counter=$((counter + 1))
    if [ $counter -gt $timeout ]; then
        echo "❌ Database connection timeout after ${timeout} seconds"
        exit 1
    fi
    echo "⏳ Waiting for Postgres... (${counter}/${timeout})"
    sleep 2
done

echo "📊 Running database migrations..."
python manage.py migrate --noinput

echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "🔍 Running Django system check..."
python manage.py check

echo "🚀 Starting Daphne ASGI server..."
exec daphne -b 0.0.0.0 -p 8000 core.asgi:application