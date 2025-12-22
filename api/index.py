"""
Vercel serverless function entry point for Django application.
This file is used by Vercel to serve the Django application.
"""
import os
import sys

# Add the CRM directory to the Python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRM_DIR = os.path.join(BASE_DIR, "CRM")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, CRM_DIR)

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application

# Get the WSGI application
# Vercel's Python runtime automatically detects WSGI applications
# and passes the request path correctly
application = get_wsgi_application()

