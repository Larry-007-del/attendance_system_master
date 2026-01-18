#!/bin/bash
# Build script for Render deployment

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

echo "Build completed successfully!"
