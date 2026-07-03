"""
Django settings for civicfix project.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "rest_framework.authtoken",
    "issues",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "civicfix.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "civicfix.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# Default: SQLite (works out of the box, zero setup, good for demo/grading).
# Production target: Oracle. Set DB_ENGINE=oracle and the ORACLE_* env vars
# to switch — no code changes needed elsewhere in the project.
# Requires: pip install oracledb  (then set ENGINE below to
# 'django.db.backends.oracle' and the oracledb driver handles the rest)
# ---------------------------------------------------------------------------
if os.environ.get("DB_ENGINE") == "oracle":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.oracle",
            "NAME": os.environ.get("ORACLE_DSN", "localhost:1521/XEPDB1"),
            "USER": os.environ.get("ORACLE_USER", "civicfix"),
            "PASSWORD": os.environ.get("ORACLE_PASSWORD", "civicfix"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "issues" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# --- Production security hardening ----------------------------------------
# All of this is inert during local dev (DEBUG=1). Once you deploy with
# DJANGO_DEBUG=0, these kick in automatically — no separate "prod settings
# file" to remember to use.
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Trust the X-Forwarded-Proto header set by Nginx/Caddy/ELB so Django
    # knows the original request was HTTPS even though it reaches gunicorn
    # over plain HTTP inside the container.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    if SECRET_KEY == "dev-secret-key-change-in-production":
        raise RuntimeError(
            "DJANGO_SECRET_KEY must be set to a real secret when DJANGO_DEBUG=0. "
            "Generate one with: python -c \"from django.core.management.utils import "
            "get_random_secret_key; print(get_random_secret_key())\""
        )

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# --- CivicFix business rules ---------------------------------------------
# SLA (hours) before an unresolved issue auto-escalates to the next tier,
# keyed by severity category.
SLA_HOURS_BY_CATEGORY = {
    "hazard": 24,      # e.g. open manhole, live wire, gas leak
    "sanitation": 72,  # garbage, drainage
    "infrastructure": 120,  # potholes, streetlights
    "other": 168,
}

# Radius (in meters) within which a new report is treated as a duplicate
# of an existing open issue in the same category.
DUPLICATE_RADIUS_METERS = 100

# ---------------------------------------------------------------------------
# Escalation tier names — CivicFix is not tied to any one country's civic
# structure. The 3-tier "local -> regional -> top authority" pattern is
# common worldwide, but the titles differ everywhere (e.g. India: Ward
# Officer -> District Head -> Municipal Commissioner; US: Ward Council ->
# City Council -> Mayor's Office; UK: Councillor -> Council -> Ombudsman).
# Override these via env vars to match your municipality; generic defaults
# are used otherwise so the project isn't hardcoded to any one region.
# ---------------------------------------------------------------------------
ESCALATION_TIER_NAMES = {
    1: os.environ.get("TIER_1_NAME", "Local Authority"),
    2: os.environ.get("TIER_2_NAME", "Regional Authority"),
    3: os.environ.get("TIER_3_NAME", "Top Authority"),
}

# ---------------------------------------------------------------------------
# Default map center shown before the browser's geolocation resolves (or if
# the person denies location access / clicks around without it). Defaults
# to a neutral world view rather than any specific city, so the app isn't
# implicitly centered on one country. Set these in .env to default the map
# to your own city/region instead.
# ---------------------------------------------------------------------------
DEFAULT_MAP_LAT = float(os.environ.get("DEFAULT_MAP_LAT", "20.0"))
DEFAULT_MAP_LNG = float(os.environ.get("DEFAULT_MAP_LNG", "0.0"))
DEFAULT_MAP_ZOOM = int(os.environ.get("DEFAULT_MAP_ZOOM", "2"))
