web: python CRM/manage.py migrate && gunicorn crm.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120
worker: celery -A crm worker -l info --concurrency=4
