#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# build.sh already handles collectstatic, migrate, and createsuperuser.
# This script only starts the application server.

echo "🔥 Starting Gunicorn..."
exec gunicorn attendance_system.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
