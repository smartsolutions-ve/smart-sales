"""
Modelos del módulo de Cuentas por Cobrar (CxC).

La deuda de un cliente se calcula como la suma de pedidos activos
menos los pagos registrados. No se replica una "factura CxC" separada.
"""
from datetime import date

from django.conf import settings
from django.db import models

from apps.pedidos.models import TenantModel


class Pago(TenantModel):
    """Registro de un cobro recibido de un cliente."""

    METODOS = [
        ('EFECTIVO',      'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('CHEQUE',        'Cheque'),
        ('ZELLE',         'Zelle'),
        ('DIVISA',        'Divisas en efectivo'),
        ('OTRO',          'Otro'),
    ]

    cliente = models.ForeignKey(
        'pedidos.Cliente',
        on_delete=models.PROTECT,
        related_name='pagos',
        verbose_name='cliente',
    )
    fecha = models.DateField(
        'Fecha de pago',
        default=date.today,
        db_index=True,
    )
    monto = models.DecimalField(
        'Monto USD',
        max_digits=12,
        decimal_places=2,
    )
    metodo = models.CharField(
        'Método',
        max_length=15,
        choices=METODOS,
        default='TRANSFERENCIA',
    )
    referencia = models.CharField(
        'N° referencia / comprobante',
        max_length=100,
        blank=True,
    )
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='registrado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f'Pago {self.cliente} — ${self.monto} ({self.fecha})'
