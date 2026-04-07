"""Utilidades para el módulo de cotizaciones."""
from django.db import transaction


def generar_numero_cotizacion(organization) -> str:
    """
    Genera el próximo número de cotización para la organización.
    Usa ConfiguracionEmpresa.get_numero_cotizacion() con select_for_update
    para garantizar unicidad bajo concurrencia.
    Si la configuración no existe, cae al método heredado.
    """
    from apps.configuracion.models import ConfiguracionEmpresa

    with transaction.atomic():
        try:
            config = (
                ConfiguracionEmpresa.objects
                .select_for_update()
                .get(organization=organization)
            )
            return config.get_numero_cotizacion()
        except ConfiguracionEmpresa.DoesNotExist:
            return _generar_numero_legacy(organization)


def _generar_numero_legacy(organization) -> str:
    """Numeración heredada: busca el último número y lo incrementa."""
    from .models import Cotizacion

    ultimo = (
        Cotizacion.objects
        .filter(organization=organization)
        .select_for_update()
        .order_by('-numero')
        .values_list('numero', flat=True)
        .first()
    )

    n = 0
    if ultimo:
        try:
            n = int(ultimo.replace('COT-', ''))
        except ValueError:
            n = 0

    return f'COT-{n + 1:04d}'
