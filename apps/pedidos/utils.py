"""Utilidades para el módulo de pedidos."""
from django.db import transaction


def generar_numero_pedido(organization) -> str:
    """
    Genera el próximo número de pedido para la organización.
    Formato: PED-XXXX (4 dígitos con cero a la izquierda).
    Usa select_for_update() para evitar condiciones de carrera.
    """
    from .models import Pedido

    with transaction.atomic():
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

        nuevo_num = ultimo_num + 1
        return f'PED-{nuevo_num:04d}'
