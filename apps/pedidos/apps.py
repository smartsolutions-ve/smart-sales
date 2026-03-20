from django.apps import AppConfig


class PedidosConfig(AppConfig):
    name = 'apps.pedidos'
    verbose_name = 'Pedidos'

    def ready(self):
        import apps.pedidos.signals  # noqa — registra las señales
