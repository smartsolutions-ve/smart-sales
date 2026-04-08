"""
Settings base compartidos entre dev y prod.
No usar directamente — usar dev.py o prod.py.
"""
import environ
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Variables de entorno ───────────────────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / '.env')

# ── Seguridad ──────────────────────────────────────────────────────────────────
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# ── Identidad de la aplicación ─────────────────────────────────────────────────
APP_NAME = env('APP_NAME', default='SmartSales')
APP_INITIALS = env('APP_INITIALS', default='SS')

# ── Aplicaciones ───────────────────────────────────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'django_htmx',
    'crispy_forms',
    'crispy_tailwind',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.pedidos',
    'apps.productos',
    'apps.despacho',
    'apps.competencia',
    'apps.campo',
    'apps.reportes',
    'apps.flotas',
    'apps.cuotas',
    'apps.chat_ia',
    'apps.configuracion',
    'apps.cotizaciones',
    'apps.cxc',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ──────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',        # Estáticos en producción
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_htmx.middleware.HtmxMiddleware',            # request.htmx
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.accounts.middleware.TenantMiddleware',        # request.org + verificar org activa
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# ── Templates ──────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.accounts.context_processors.app_settings',
                'apps.configuracion.context_processors.tasa_cambio',
            ],
        },
    },
]

# ── Base de datos ──────────────────────────────────────────────────────────────
DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///db.sqlite3')
}

# ── Auth ───────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# ── Internacionalización ────────────────────────────────────────────────────────
LANGUAGE_CODE = 'es-ve'
TIME_ZONE = 'America/Caracas'
USE_I18N = True
USE_TZ = True

# ── Archivos estáticos ──────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Archivos media ──────────────────────────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Campo por defecto ────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Crispy Forms ────────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'tailwind'
CRISPY_TEMPLATE_PACK = 'tailwind'

# ── Sesiones ────────────────────────────────────────────────────────────────────
SESSION_COOKIE_AGE = 8 * 60 * 60       # 8 horas en segundos
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Expira al cerrar browser

# ── Email ───────────────────────────────────────────────────────────────────────
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@smartsales.com.ve')

# ── Chat IA ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')
OPENROUTER_API_KEY = env('OPENROUTER_API_KEY', default='')
OPENROUTER_MODEL = env('OPENROUTER_MODEL', default='deepseek/deepseek-chat:free')
CHAT_IA_BACKEND = env('CHAT_IA_BACKEND', default='apps.chat_ia.services.openrouter.OpenRouterBackend')
CHAT_IA_HISTORY_LENGTH = 10
CHAT_IA_RATE_LIMIT_HOUR = 30
