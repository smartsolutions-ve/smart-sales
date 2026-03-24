"""Settings para PythonAnywhere (staging/demo)."""
from .base import *  # noqa

DEBUG = False

# PythonAnywhere maneja HTTPS a nivel de proxy
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# CSRF trusted origins — cambiar 'tuusuario' por tu usuario de PythonAnywhere
CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=['https://tuusuario.pythonanywhere.com'],
)

# Email: imprimir en consola (no enviar en demo)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Logging basico
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}
