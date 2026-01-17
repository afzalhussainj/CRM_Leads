import os
from datetime import timedelta

from corsheaders.defaults import default_headers
from dotenv import load_dotenv


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# SECURITY WARNING: keep the secret key used in production secret!
# For local development, fall back to a dummy key if not provided
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "1").lower() in ("1", "true", "yes")


# ALLOWED_HOSTS: Support Render, Vercel, Railway, and custom hosts via env, with smart defaults
_allowed_hosts_env = os.getenv("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(",") if h.strip()]

# Automatically allow Render.com hostname
# Render automatically sets RENDER_EXTERNAL_HOSTNAME env var (e.g., "crm-leads-cwml.onrender.com")
render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if render_host:
    # Remove port if present
    render_host_clean = render_host.split(":")[0]
    if render_host_clean not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(render_host_clean)

# Automatically allow Vercel hostname
# Vercel sets VERCEL_URL env var (e.g., "your-app.vercel.app")
vercel_url = os.getenv("VERCEL_URL")
if vercel_url:
    # Remove protocol if present
    vercel_host = vercel_url.replace("https://", "").replace("http://", "").split("/")[0]
    if vercel_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_host)
    # Also add without port
    vercel_host_clean = vercel_host.split(":")[0]
    if vercel_host_clean not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_host_clean)

# Automatically allow Railway hostname
# Railway sets RAILWAY_STATIC_URL or PUBLIC_URL env var
railway_url = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if railway_url:
    # Railway provides the full domain (e.g., "app-production.up.railway.app")
    railway_host = railway_url.replace("https://", "").replace("http://", "").split("/")[0]
    if railway_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(railway_host)

# Always allow localhost for local development (frontend testing)
localhost_hosts = ["localhost", "127.0.0.1", "0.0.0.0"]
for host in localhost_hosts:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

# Fallback to localhost if no hosts are configured
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = localhost_hosts

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "phonenumber_field",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "common",
    "leads",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # CORS middleware should be as early as possible
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "crum.CurrentRequestUserMiddleware",
    "common.middleware.get_company.GetProfile",
]

ROOT_URLCONF = "crm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "utils.context_processors.role_constants",
            ],
        },
    },
]

WSGI_APPLICATION = "crm.wsgi.application"

# Database: Prefer DATABASE_URL (Supabase/Render). Fallback to existing env-based config, else SQLite
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Fix for Supabase: Use connection pooler (port 6543) if it's a Supabase URL
    # Also handle IPv6 issues by forcing IPv4 or using pooler
    if "supabase.co" in DATABASE_URL and ":5432" in DATABASE_URL:
        # Replace direct connection (5432) with connection pooler (6543)
        DATABASE_URL = DATABASE_URL.replace(":5432", ":6543")
        # Ensure sslmode=require is present
        if "sslmode" not in DATABASE_URL:
            separator = "&" if "?" in DATABASE_URL else "?"
            DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"
    
    try:
        import dj_database_url  # type: ignore
        db_config = dj_database_url.parse(DATABASE_URL, conn_max_age=600)
        # Additional Supabase connection settings
        if "supabase.co" in DATABASE_URL:
            db_config["OPTIONS"] = {
                "connect_timeout": 10,
                "sslmode": "require",
            }
        DATABASES = {"default": db_config}
    except Exception as e:
        print(f"Error parsing DATABASE_URL: {e}")
        # Minimal manual parse fallback if dj-database-url isn't available
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.getenv("DBNAME", "postgres"),
                "USER": os.getenv("DBUSER", "postgres"),
                "PASSWORD": os.getenv("DBPASSWORD", ""),
                "HOST": os.getenv("DBHOST", "127.0.0.1"),
                "PORT": os.getenv("DBPORT", "5432"),
            }
        }
elif os.getenv("DBNAME") or os.getenv("DB_ENGINE", "").lower().startswith("postgres"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DBNAME", "crm"),
            "USER": os.getenv("DBUSER", "crm"),
            "PASSWORD": os.getenv("DBPASSWORD", "crm"),
            "HOST": os.getenv("DBHOST", "127.0.0.1"),
            "PORT": os.getenv("DBPORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/


TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True

# Email Configuration
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = os.getenv("EMAIL_HOST", "")
# EMAIL_PORT = int(os.getenv("EMAIL_PORT", ""))
# EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "").lower() == "true"
# EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
# EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Email configuration (Mailtrap SMTP)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "sandbox.smtp.mailtrap.io"
EMAIL_PORT = 2525
EMAIL_HOST_USER = "e5850c021f3e0d"
EMAIL_HOST_PASSWORD = "e8d3e674b2bfb5"
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = "no-reply@example.com"



# Site URL for email links
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")

# Frontend URL (React app hosted on Vercel)
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://slcwcrm.vercel.app")
FRONTEND_LOGIN_URL = f"{FRONTEND_URL}/login"

# Django login URL - redirect to frontend
LOGIN_URL = FRONTEND_LOGIN_URL

AUTH_USER_MODEL = "common.User"

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

ENV_TYPE = os.getenv("ENV_TYPE", "dev")
print(">>> ENV_TYPE", ENV_TYPE)
if ENV_TYPE == "dev":
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
    MEDIA_URL = "/media/"

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "dev@example.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")

# celery Tasks
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Normalize Redis URLs: force database 0 and add SSL parameters for rediss://
def normalize_redis_url(url):
    """Normalize Redis URL to add SSL parameters for rediss://"""
    if not url or "//" not in url:
        return url
    
    # For rediss:// URLs, add ssl_cert_reqs parameter if not already present (required in Celery 5.4+)
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}ssl_cert_reqs=CERT_NONE"
    
    return url

CELERY_BROKER_URL = normalize_redis_url(CELERY_BROKER_URL)
CELERY_RESULT_BACKEND = normalize_redis_url(CELERY_RESULT_BACKEND)

# Celery configuration
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'



LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "formatters": {
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[%(server_time)s] %(message)s",
        }
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
        },
        "console_debug_false": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "logging.StreamHandler",
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": [
                "console",
                "console_debug_false",
            ],
            "level": "INFO",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

APPLICATION_NAME = "bottlecrm"


SETTINGS_EXPORT = ["APPLICATION_NAME"]

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "common.utils.external_auth.CustomDualAuthentication"
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 10
}

# CORS Configuration
CORS_ALLOW_CREDENTIALS = True  # Required for HTTP-only cookies
CORS_PREFLIGHT_MAX_AGE = 86400  # Cache preflight requests for 24 hours
CORS_ALLOW_HEADERS = list(default_headers) + [
    'content-type',
    'authorization',
    'x-csrftoken',
    'x-requested-with',
    'accept',
    'accept-encoding',
    'accept-language',
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_EXPOSE_HEADERS = [
    'content-type',
    'authorization',
]

# CORS Allowed Origins - simple configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  
    "https://slcwcrm.vercel.app",  
]

# Add frontend URL from environment variable (Vercel) if different
if FRONTEND_URL:
    # Ensure no trailing slash
    frontend_url_clean = FRONTEND_URL.rstrip('/')
    if frontend_url_clean not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(frontend_url_clean)

CORS_ORIGIN_ALLOW_ALL = False

# CSRF Trusted Origins - same as CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS.copy()

SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DOMAIN_NAME = os.getenv("DOMAIN_NAME", "localhost")

# Cookie settings for HTTP-only JWT tokens
JWT_COOKIE_NAME = "access_token"
JWT_REFRESH_COOKIE_NAME = "refresh_token"
JWT_COOKIE_SECURE = True  
JWT_COOKIE_HTTPONLY = True  
JWT_COOKIE_SAMESITE = "None"
JWT_COOKIE_DOMAIN = None

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=365),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
JWT_ALGO = "HS256"

