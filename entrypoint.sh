#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# build.sh handles collectstatic, but migrations must also run at startup
# in case the build step ran before DATABASE_URL was available.

echo "🔄 Running migrations..."
python manage.py migrate --no-input

echo "� Collecting static files..."
python manage.py collectstatic --no-input

echo "📂 Static files in STATIC_ROOT:"
ls -la staticfiles/css/ 2>/dev/null || echo "  (no css directory)"
ls -la staticfiles/js/ 2>/dev/null || echo "  (no js directory)"

echo "�🔥 Starting Gunicorn..."
exec gunicorn attendance_system.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
