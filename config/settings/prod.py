"""Settings de producción (Render)."""
from .base import *  # noqa

DEBUG = False

# ── Seguridad HTTPS ────────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── CSRF trusted origins (requerido en Django 4+ con HTTPS) ──────────────────
CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=[
        'https://smartsales-u8dw.onrender.com',
        'https://smartsales.app',
        'https://www.smartsales.app',
    ],
)

# ── Email con Resend ───────────────────────────────────────────────────────────
EMAIL_BACKEND = 'anymail.backends.resend.EmailBackend'
ANYMAIL = {
    'RESEND_API_KEY': env('RESEND_API_KEY'),
}

# ── Logging en producción ──────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
