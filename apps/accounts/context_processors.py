from django.conf import settings


def app_settings(request):
    """Inyecta variables de configuración de la app en todos los templates."""
    return {
        'APP_NAME': getattr(settings, 'APP_NAME', 'SmartSales'),
        'APP_INITIALS': getattr(settings, 'APP_INITIALS', 'SS'),
    }
