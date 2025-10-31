#!/bin/sh
set -e

echo "🚀 Starting CRM application..."

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "📊 Running database migrations..."
python manage.py migrate --verbosity 2

echo "✅ Setup completed successfully!"
echo "🌐 Starting Gunicorn server..."

# Start Gunicorn
exec gunicorn crm.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
