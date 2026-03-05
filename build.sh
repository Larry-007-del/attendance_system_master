#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install Python Dependencies
pip install -r requirements.txt

# 2. Install Node.js Dependencies & Build Frontend Assets
if command -v node &> /dev/null; then
  npm ci --production=false
  npm run build
fi

# 3. Collect Static Files (CSS/JS)
python manage.py collectstatic --no-input

# 4. Apply Database Migrations
python manage.py migrate

# 5. Create Superuser (Automatically)
# This command checks environment variables and creates the user if they don't exist
python manage.py createsuperuser --no-input --email "$DJANGO_SUPERUSER_EMAIL" || true
