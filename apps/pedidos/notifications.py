"""Notificaciones por email para el módulo de pedidos."""
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)


def notificar_cambio_estado(pedido, estado_anterior, usuario_que_cambio):
    """Envía email al vendedor cuando cambia el estado de su pedido."""
    vendedor = pedido.vendedor
    if not vendedor.email:
        return

    asunto = f'Pedido {pedido.numero} — Estado actualizado a {pedido.estado}'

    mensaje = (
        f'Hola {vendedor.get_full_name() or vendedor.username},\n\n'
        f'El pedido {pedido.numero} del cliente {pedido.cliente} '
        f'cambió de estado:\n\n'
        f'  Estado anterior: {estado_anterior}\n'
        f'  Nuevo estado: {pedido.estado}\n\n'
        f'Cambio realizado por: {usuario_que_cambio.get_full_name() or usuario_que_cambio.username}\n\n'
        f'— SmartSales'
    )

    try:
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendedor.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning(f'Error enviando notificación de pedido {pedido.numero}: {e}')


def notificar_pedido_nuevo_campo(pedido):
    """Notifica a gerentes cuando un vendedor crea pedido desde campo."""
    from apps.accounts.models import User
    gerentes = User.objects.filter(
        organization=pedido.organization,
        role='gerente',
        is_active=True,
    ).exclude(email='')

    if not gerentes:
        return

    emails = [g.email for g in gerentes]
    try:
        send_mail(
            subject=f'Nuevo pedido {pedido.numero} desde campo',
            message=f'{pedido.vendedor.get_full_name() or pedido.vendedor.username} ha creado el pedido {pedido.numero} para {pedido.cliente} por ${pedido.total}.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=emails,
            fail_silently=True,
        )
    except Exception as e:
        logger.warning(f'Error enviando notificación de pedido campo {pedido.numero}: {e}')
