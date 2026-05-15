#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Migrations run here (not just in build.sh) in case DATABASE_URL was unavailable
# during the build step. collectstatic also runs here as a safety net so static
# files are always served correctly even if the build step had issues.

echo "🔄 Running migrations..."
python manage.py migrate --no-input

echo "📦 Collecting static files..."
python manage.py collectstatic --no-input

# Create superuser if env vars are set (skip if user already exists)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  echo "👤 Ensuring superuser exists..."
  python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
import os
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username=username,
        email=os.environ.get('DJANGO_SUPERUSER_EMAIL', ''),
        password=os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    )
    print(f'Superuser \"{username}\" created.')
else:
    print(f'Superuser \"{username}\" already exists, skipping.')
"
fi
: "${PORT:=10000}"
WORKERS="${WEB_CONCURRENCY:-2}"

echo "🔥 Starting Gunicorn on port ${PORT} with ${WORKERS} workers..."
exec gunicorn attendance_system.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WORKERS}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
