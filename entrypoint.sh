#!/bin/bash
set -e

echo "🚀 Starting ZamIO Django Application..."

# Function to check if a service is ready
wait_for_service() {
    local service_name=$1
    local service_url=$2
    local timeout=${3:-60}
    local counter=0
    
    echo "⏳ Waiting for $service_name connection..."
    until python -c "
import os, sys
try:
    if '$service_name' == 'postgres':
        import psycopg2
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        conn.close()
        print('✅ Database connected successfully')
    elif '$service_name' == 'redis':
        import redis
        r = redis.from_url(os.environ['REDIS_URL'])
        r.ping()
        print('✅ Redis connected successfully')
    sys.exit(0)
except Exception as e:
    print(f'❌ $service_name connection failed: {e}')
    sys.exit(1)
" 2>/dev/null; do
        counter=$((counter + 1))
        if [ $counter -gt $timeout ]; then
            echo "❌ $service_name connection timeout after ${timeout} seconds"
            exit 1
        fi
        echo "⏳ Waiting for $service_name... (${counter}/${timeout})"
        sleep 2
    done
}

# Wait for database
wait_for_service "postgres" "$DATABASE_URL" 60

# Wait for Redis
wait_for_service "redis" "$REDIS_URL" 30

echo "📊 Running database migrations..."
python manage.py migrate --noinput

echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "🔍 Running Django system check..."
python manage.py check --deploy

echo "🚀 Starting Daphne ASGI server..."
exec daphne -b 0.0.0.0 -p 8000 core.asgi:application