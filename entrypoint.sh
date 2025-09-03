#!/bin/bash

# Local development entrypoint for ZamIO Django
set -e

log() {
	echo "$(date +"%Y-%m-%d %H:%M:%S.%3N") | $1"
}

log "Starting ZamIO Django application..."

# Wait for database to be ready using pg_isready
log "Waiting for database to be ready..."
until pg_isready -h db -p 5432 -U zamio_user -d zamio_local >/dev/null 2>&1; do
	log "Database is not ready yet. Waiting..."
	sleep 2
done

# If a command is provided (e.g., Celery), run it; otherwise do Django setup and start server
if [ "$#" -gt 0 ]; then
	log "Executing provided command (skipping makemigrations/migrate): $*"
	exec "$@"
else
	## Run makemigrations (dev convenience)
	#log "Running database make migrations..."
	#python manage.py makemigrations || true

	# Run migrations
	log "Running database migrations..."
	python manage.py migrate

	# Collect static files (if needed)
	log "Collecting static files..."
	python manage.py collectstatic --noinput || true

	# Start the application
	log "Starting Django development server..."
	exec python manage.py runserver 0.0.0.0:8000
fi
