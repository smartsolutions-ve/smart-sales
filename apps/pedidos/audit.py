"""Funciones de auditoría para el módulo de pedidos."""
from .models import PedidoLog


def log_pedido(pedido, usuario, accion, detalle=''):
    """Registra una entrada de auditoría para un pedido."""
    PedidoLog.objects.create(
        pedido=pedido,
        usuario=usuario,
        accion=accion,
        detalle=detalle,
    )
