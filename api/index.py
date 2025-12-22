import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application

BASE_DIR = Path(__file__).resolve().parent.parent  # repo root
CRM_DIR = BASE_DIR / "CRM"

# Ensure Django project is importable
sys.path.insert(0, str(CRM_DIR))

# IMPORTANT: this must match your settings module path exactly (case-sensitive)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")

# Create WSGI app
app = get_wsgi_application()

