import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "organizations",
    "catalog",
    "inventory",
    "customers",
    "orders",
    "sales",
    "electronic_tax",
    "administration",
    "portal",
    "external_payments",
    "transactional_notifications",
    "reports",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "mysql").strip().lower()
if DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ["DB_USER"],
            "PASSWORD": os.environ["DB_PASSWORD"],
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
elif DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.getenv("SQLITE_PATH", BASE_DIR / "db.sqlite3")),
        }
    }
else:
    raise RuntimeError("DB_ENGINE debe ser 'mysql' o 'sqlite'.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"

AUTH_USER_MODEL = "accounts.User"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:4200,http://127.0.0.1:4200,http://localhost:4300,http://127.0.0.1:4300",
)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", False)
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)

# SII DTE adapter. Secrets are supplied through environment variables or files.
SII_ADAPTER_ENABLED = env_bool("SII_ADAPTER_ENABLED", False)
SII_ENVIRONMENT = os.getenv("SII_ENVIRONMENT", "certification").strip().lower()
SII_CERTIFICATE_PFX_PATH = os.getenv("SII_CERTIFICATE_PFX_PATH", "").strip()
SII_CERTIFICATE_PASSWORD_ENV = os.getenv("SII_CERTIFICATE_PASSWORD_ENV", "SII_CERTIFICATE_PASSWORD").strip()
SII_SENDER_RUT = os.getenv("SII_SENDER_RUT", "").strip()
SII_SECRET_KEY = os.getenv("SII_SECRET_KEY", "").strip()
SII_XSD_DIR = os.getenv("SII_XSD_DIR", "").strip()
SII_CAF_TRUSTED_PUBLIC_KEYS_DIR = os.getenv("SII_CAF_TRUSTED_PUBLIC_KEYS_DIR", "").strip()
SII_HTTP_TIMEOUT = float(os.getenv("SII_HTTP_TIMEOUT", "20"))

SII_EXCHANGE_ENABLED = env_bool("SII_EXCHANGE_ENABLED", False)
SII_EXCHANGE_FROM_EMAIL = os.getenv("SII_EXCHANGE_FROM_EMAIL", "").strip()
SII_EXCHANGE_XSD_DIR = os.getenv("SII_EXCHANGE_XSD_DIR", SII_XSD_DIR).strip()

ELECTRONIC_TAX_FOLIO_LOW_THRESHOLD = int(os.getenv("ELECTRONIC_TAX_FOLIO_LOW_THRESHOLD", "25"))
ELECTRONIC_TAX_CERTIFICATE_WARNING_DAYS = int(os.getenv("ELECTRONIC_TAX_CERTIFICATE_WARNING_DAYS", "30"))
ELECTRONIC_TAX_STALE_MINUTES = int(os.getenv("ELECTRONIC_TAX_STALE_MINUTES", "30"))
ELECTRONIC_TAX_STATUS_RETRY_MINUTES = int(os.getenv("ELECTRONIC_TAX_STATUS_RETRY_MINUTES", "5"))
ELECTRONIC_TAX_STATUS_RETRY_MAX_ATTEMPTS = int(os.getenv("ELECTRONIC_TAX_STATUS_RETRY_MAX_ATTEMPTS", "8"))

# Transactional email uses an outbox. Credentials remain environment-only.
TRANSACTIONAL_EMAIL_ENABLED = env_bool("TRANSACTIONAL_EMAIL_ENABLED", False)
TRANSACTIONAL_EMAIL_BACKEND = os.getenv(
    "TRANSACTIONAL_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
).strip()
TRANSACTIONAL_EMAIL_HOST = os.getenv("TRANSACTIONAL_EMAIL_HOST", "").strip()
TRANSACTIONAL_EMAIL_PORT = int(os.getenv("TRANSACTIONAL_EMAIL_PORT", "587"))
TRANSACTIONAL_EMAIL_USE_TLS = env_bool("TRANSACTIONAL_EMAIL_USE_TLS", True)
TRANSACTIONAL_EMAIL_USE_SSL = env_bool("TRANSACTIONAL_EMAIL_USE_SSL", False)
TRANSACTIONAL_EMAIL_REQUIRE_AUTH = env_bool("TRANSACTIONAL_EMAIL_REQUIRE_AUTH", True)
TRANSACTIONAL_EMAIL_USERNAME_ENV = os.getenv(
    "TRANSACTIONAL_EMAIL_USERNAME_ENV", "TRANSACTIONAL_EMAIL_USERNAME"
).strip()
TRANSACTIONAL_EMAIL_PASSWORD_ENV = os.getenv(
    "TRANSACTIONAL_EMAIL_PASSWORD_ENV", "TRANSACTIONAL_EMAIL_PASSWORD"
).strip()
TRANSACTIONAL_EMAIL_FROM = os.getenv("TRANSACTIONAL_EMAIL_FROM", "no-reply@localhost").strip().lower()
TRANSACTIONAL_EMAIL_TIMEOUT = float(os.getenv("TRANSACTIONAL_EMAIL_TIMEOUT", "15"))
TRANSACTIONAL_EMAIL_MAX_ATTEMPTS = int(os.getenv("TRANSACTIONAL_EMAIL_MAX_ATTEMPTS", "5"))
TRANSACTIONAL_EMAIL_RETRY_MINUTES = int(os.getenv("TRANSACTIONAL_EMAIL_RETRY_MINUTES", "5"))
TRANSACTIONAL_EMAIL_SENDING_STALE_MINUTES = int(os.getenv("TRANSACTIONAL_EMAIL_SENDING_STALE_MINUTES", "30"))

# Mercado Pago Checkout Pro. Credentials are resolved from environment variables.
MERCADO_PAGO_ENABLED = env_bool("MERCADO_PAGO_ENABLED", False)
MERCADO_PAGO_ACCESS_TOKEN_ENV = os.getenv("MERCADO_PAGO_ACCESS_TOKEN_ENV", "MERCADO_PAGO_ACCESS_TOKEN").strip()
MERCADO_PAGO_WEBHOOK_SECRET_ENV = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET_ENV", "MERCADO_PAGO_WEBHOOK_SECRET").strip()
MERCADO_PAGO_API_BASE_URL = os.getenv("MERCADO_PAGO_API_BASE_URL", "https://api.mercadopago.com").strip()
MERCADO_PAGO_RETURN_BASE_URL = os.getenv("MERCADO_PAGO_RETURN_BASE_URL", "").strip()
MERCADO_PAGO_WEBHOOK_URL = os.getenv("MERCADO_PAGO_WEBHOOK_URL", "").strip()
MERCADO_PAGO_HTTP_TIMEOUT = float(os.getenv("MERCADO_PAGO_HTTP_TIMEOUT", "15"))
MERCADO_PAGO_USE_SANDBOX_INIT_POINT = env_bool("MERCADO_PAGO_USE_SANDBOX_INIT_POINT", False)
MERCADO_PAGO_ACCEPT_LIVE_MODE = env_bool("MERCADO_PAGO_ACCEPT_LIVE_MODE", False)
