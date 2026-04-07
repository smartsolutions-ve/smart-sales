"""Utilidades para el módulo de pedidos."""
from django.db import transaction


def generar_numero_pedido(organization) -> str:
    """
    Genera el próximo número de pedido para la organización.
    Usa ConfiguracionEmpresa.get_numero_pedido() con select_for_update para garantizar
    unicidad bajo concurrencia. Si la configuración no existe aún, cae al método heredado.
    """
    from apps.configuracion.models import ConfiguracionEmpresa

    with transaction.atomic():
        try:
            config = (
                ConfiguracionEmpresa.objects
                .select_for_update()
                .get(organization=organization)
            )
            return config.get_numero_pedido()
        except ConfiguracionEmpresa.DoesNotExist:
            return _generar_numero_legacy(organization)


def _generar_numero_legacy(organization) -> str:
    """Numeración heredada: busca el último número y lo incrementa."""
    from .models import Pedido

    ultimo = (
        Pedido.objects
        .filter(organization=organization)
        .select_for_update()
        .order_by('-numero')
        .values_list('numero', flat=True)
        .first()
    )

    if ultimo:
        try:
            ultimo_num = int(ultimo.replace('PED-', ''))
        except ValueError:
            ultimo_num = 0
    else:
        ultimo_num = 0

    return f'PED-{ultimo_num + 1:04d}'
