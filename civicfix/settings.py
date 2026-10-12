import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "issues",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "issues.middleware.UserPreferencesMiddleware",
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
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "civicfix.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_DB", BASE_DIR / "db.sqlite3"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
LANGUAGES = [("en", "English"), ("hi", "हिन्दी"), ("or", "ଓଡ଼ିଆ")]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "issues" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_SUPPORT_ROOT = Path(os.environ.get("PRIVATE_SUPPORT_ROOT", BASE_DIR / "private_support"))

# Allow the 5 MB photo limit plus multipart overhead while bounding parsed data.
DATA_UPLOAD_MAX_MEMORY_SIZE = 26 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 10

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "landing"
LOGOUT_REDIRECT_URL = "landing"
# Use the development console backend until SMTP credentials are configured.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").strip().lower() in {"1", "true", "yes", "on"}
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "civicfix.team@gmail.com").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "CivicFix Team <civicfix.team@gmail.com>"
).strip()
CONTACT_RECEIVER_EMAIL = os.environ.get(
    "CONTACT_RECEIVER_EMAIL", "civicfix.team@gmail.com"
).strip()
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_PASSWORD
    else "django.core.mail.backends.console.EmailBackend",
)
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000")

CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    if SECRET_KEY == "dev-secret-key-change-in-production":
        raise RuntimeError("Set DJANGO_SECRET_KEY in .env before running with DEBUG=0")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# radius (meters) within which a new report counts as a duplicate
DUPLICATE_RADIUS_METERS = 100


DEFAULT_MAP_LAT = float(os.environ.get("DEFAULT_MAP_LAT", "20.5937"))
DEFAULT_MAP_LNG = float(os.environ.get("DEFAULT_MAP_LNG", "78.9629"))
DEFAULT_MAP_ZOOM = int(os.environ.get("DEFAULT_MAP_ZOOM", "5"))

GEOCODING_BASE_URL = os.environ.get("GEOCODING_BASE_URL", "https://nominatim.openstreetmap.org").rstrip("/")
GEOCODING_USER_AGENT = os.environ.get("GEOCODING_USER_AGENT", "CivicFix/1.0 (civic issue reporting)")

LOG_DIR = os.environ.get("LOG_DIR", "")
_handlers = {
    "console": {
        "class": "logging.StreamHandler",
        "formatter": "simple",
    },
}
_root_handlers = ["console"]

if LOG_DIR:
    os.makedirs(LOG_DIR, exist_ok=True)
    _handlers["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": os.path.join(LOG_DIR, "civicfix.log"),
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 3,
        "formatter": "verbose",
    }
    _root_handlers.append("file")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
        "verbose": {"format": "[{levelname}] {asctime} {name} {module}.{funcName}:{lineno}: {message}", "style": "{"},
    },
    "handlers": _handlers,
    "root": {"handlers": _root_handlers, "level": "INFO"},
    "loggers": {
        "django": {"handlers": _root_handlers, "level": "INFO", "propagate": False},
        "django.request": {"handlers": _root_handlers, "level": "ERROR", "propagate": False},
        "issues": {"handlers": _root_handlers, "level": "INFO", "propagate": False},
    },
}

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"