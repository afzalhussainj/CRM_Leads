import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application

BASE_DIR = Path(__file__).resolve().parent.parent
CRM_DIR = BASE_DIR / "CRM"

sys.path.insert(0, str(CRM_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")

app = get_wsgi_application()

