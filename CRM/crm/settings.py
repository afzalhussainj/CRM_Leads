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


# ALLOWED_HOSTS: Support Render and custom hosts via env, with smart defaults
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

# Fallback to localhost for local development
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

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
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Site URL for email links
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")

# Frontend URL (React app hosted on Vercel)
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://skycrm.vercel.app")
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

# Caching Configuration
# Try to use Redis cache if available, otherwise fallback to local memory
cache_backend = os.getenv("CACHE_BACKEND", "locmem")
if cache_backend == "redis" and CELERY_BROKER_URL and "redis" in CELERY_BROKER_URL.lower():
    try:
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': os.getenv("CACHE_URL", "redis://localhost:6379/2"),
                'KEY_PREFIX': 'crm_leads',
                'TIMEOUT': 3600,  # Default cache timeout: 1 hour
            }
        }
    except Exception:
        # Fallback to local memory if Redis cache fails
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'unique-snowflake',
            }
        }
else:
    # Use local memory cache (works without Redis)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }


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
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.coreapi.AutoSchema",
}




# JWT_SETTINGS = {
#     'bearerFormat': ('Bearer', 'jwt', 'Jwt')
# }



CORS_ALLOW_HEADERS = default_headers
CORS_ORIGIN_ALLOW_ALL = True
# CSRF Trusted Origins - fully configurable via environment variables
_csrf_env = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = []

# Add Render wildcard if on Render (can be overridden via env)
if render_host or os.getenv("CSRF_INCLUDE_RENDER", "1").lower() in ("1", "true", "yes"):
    CSRF_TRUSTED_ORIGINS.append("https://*.onrender.com")

# Automatically add frontend URL if set
if FRONTEND_URL:
    CSRF_TRUSTED_ORIGINS.append(FRONTEND_URL)

# Add any additional origins from environment variable
if _csrf_env:
    CSRF_TRUSTED_ORIGINS.extend([o.strip() for o in _csrf_env.split(",") if o.strip()])

SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

DOMAIN_NAME = os.getenv("DOMAIN_NAME", "localhost")


SIMPLE_JWT = {
    #'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1),
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
# it is needed in custome middlewere to get the user from the token
JWT_ALGO = "HS256"


DOMAIN_NAME = os.getenv("DOMAIN_NAME", DOMAIN_NAME)

