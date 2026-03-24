"""Settings para Render.com (staging/demo gratuito)."""
from .base import *  # noqa

DEBUG = False

# ── Seguridad ────────────────────────────────────────────────────────────────
# Render termina SSL en su proxy; la app recibe HTTP internamente
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ── Hosts permitidos ─────────────────────────────────────────────────────────
# Render asigna un dominio .onrender.com automaticamente
ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=['localhost', '.onrender.com'],
)

# ── CSRF trusted origins ────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=['https://*.onrender.com'],
)

# ── Base de datos ────────────────────────────────────────────────────────────
# Render provee DATABASE_URL automaticamente al vincular un PostgreSQL.
# Si no hay DATABASE_URL, usa SQLite como fallback (filesystem efimero).
import dj_database_url
DATABASES['default'] = dj_database_url.config(
    default='sqlite:///db.sqlite3',
    conn_max_age=600,
    conn_health_checks=True,
)

# ── Archivos estaticos (WhiteNoise) ─────────────────────────────────────────
# Ya configurado en base.py, pero nos aseguramos
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Email: consola (no enviar en demo) ───────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ── Logging ──────────────────────────────────────────────────────────────────
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
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
