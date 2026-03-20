"""Settings de desarrollo local."""
from .base import *  # noqa

DEBUG = True

# En dev: SQLite para inicio rápido (sobreescribir con DATABASE_URL en .env para usar Postgres)
INSTALLED_APPS += ['debug_toolbar']

MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE

INTERNAL_IPS = ['127.0.0.1']

# En dev no usar CompressedManifestStaticFilesStorage (requiere collectstatic)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'


# Email: imprime en consola (no envía)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Logging detallado en dev
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',   # Muestra queries SQL en consola
            'propagate': False,
        },
    },
}
