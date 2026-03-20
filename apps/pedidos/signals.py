"""
Señales para mantener el total del pedido actualizado automáticamente.
Se ejecutan después de guardar o eliminar un PedidoItem.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import PedidoItem


@receiver(post_save, sender=PedidoItem)
def recalcular_total_al_guardar(sender, instance, **kwargs):
    """Recalcula el total del pedido cuando se guarda un ítem."""
    instance.pedido.recalcular_total()


@receiver(post_delete, sender=PedidoItem)
def recalcular_total_al_eliminar(sender, instance, **kwargs):
    """Recalcula el total del pedido cuando se elimina un ítem."""
    instance.pedido.recalcular_total()
