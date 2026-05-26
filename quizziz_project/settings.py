"""
Django settings for quizziz_project project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dgdfddthry5675t76m8o-=9090070=+-+*g"

DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

ALLOWED_HOSTS = ["api-dev.quizzes.ru"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "main",
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

ROOT_URLCONF = "quizziz_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": ["main/templates"],
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

WSGI_APPLICATION = "quizziz_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

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

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = "/home/site1/app/static/"
STATICFILES_DIRS = [BASE_DIR / "main" / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

CSRF_TRUSTED_ORIGINS = ["http://188.127.251.236:8081"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Директория для логов
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ============================================================
# НАСТРОЙКИ ЛОГИРОВАНИЯ
# ============================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "DEBUG",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "django.log"),
            "formatter": "verbose",
            "encoding": "utf-8",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "level": "INFO",
        },
        "errors_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "errors.log"),
            "formatter": "verbose",
            "encoding": "utf-8",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "level": "WARNING",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "main.views": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "main.views_features.views_quiz": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "main.views_features.views_admin": {
            "handlers": ["console", "file", "errors_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "main.views_features.views_lobby": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "main.views_features.views_profile": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "main.models": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "errors_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console", "errors_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
#test
