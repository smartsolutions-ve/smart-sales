from django.apps import AppConfig


class ConfiguracionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.configuracion'
    verbose_name = 'Configuración'

    def ready(self):
        import apps.configuracion.signals  # noqa: F401 — registra señales
