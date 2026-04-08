"""
Modelos del módulo de Devoluciones y Notas de Crédito.

Una devolución es el proceso inverso de un pedido entregado:
el cliente regresa mercancía, se registra la devolución,
y se crea una Nota de Crédito por el monto devuelto.
El inventario puede reingresarse como nuevo lote.
"""
from datetime import date

from django.conf import settings
from django.db import models

from apps.pedidos.models import TenantModel


class Devolucion(TenantModel):
    """Encabezado de devolución asociado a un pedido."""

    MOTIVOS = [
        ('DEFECTO', 'Producto defectuoso'),
        ('ERROR_PEDIDO', 'Error en pedido'),
        ('NO_SOLICITADO', 'Producto no solicitado'),
        ('DANO_TRANSPORTE', 'Daño en transporte'),
        ('VENCIDO', 'Producto vencido/próximo a vencer'),
        ('OTRO', 'Otro motivo'),
    ]

    ESTADOS = [
        ('Pendiente', 'Pendiente de revisión'),
        ('Aprobada', 'Aprobada'),
        ('Rechazada', 'Rechazada'),
        ('Completada', 'Completada'),
    ]

    pedido = models.ForeignKey(
        'pedidos.Pedido',
        on_delete=models.PROTECT,
        related_name='devoluciones',
        verbose_name='pedido origen',
    )
    cliente = models.ForeignKey(
        'pedidos.Cliente',
        on_delete=models.PROTECT,
        related_name='devoluciones',
        verbose_name='cliente',
    )
    fecha = models.DateField('fecha', default=date.today, db_index=True)
    motivo = models.CharField('motivo', max_length=20, choices=MOTIVOS)
    estado = models.CharField(
        'estado', max_length=12, choices=ESTADOS, default='Pendiente', db_index=True
    )
    observaciones = models.TextField('observaciones', blank=True)
    monto_credito = models.DecimalField(
        'monto nota de crédito', max_digits=12, decimal_places=2, default=0
    )
    reingresar_inventario = models.BooleanField(
        'reingresar al inventario', default=True
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name='registrado por',
    )
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='aprobado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Devolución'
        verbose_name_plural = 'Devoluciones'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f'DEV-{self.pk} — {self.cliente} ({self.fecha})'

    def calcular_monto(self):
        """Suma el monto de todos los ítems devueltos y actualiza monto_credito."""
        from django.db.models import DecimalField, ExpressionWrapper, F, Sum
        resultado = self.items.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('cantidad') * F('precio_unitario'),
                    output_field=DecimalField(),
                )
            )
        )
        self.monto_credito = resultado['total'] or 0
        self.save(update_fields=['monto_credito'])
        return self.monto_credito

    def puede_aprobar(self):
        """Solo las devoluciones pendientes pueden aprobarse."""
        return self.estado == 'Pendiente'

    def puede_completar(self):
        """Solo las devoluciones aprobadas pueden completarse."""
        return self.estado == 'Aprobada'

    def puede_rechazar(self):
        """Solo las devoluciones pendientes pueden rechazarse."""
        return self.estado == 'Pendiente'


class DevolucionItem(TenantModel):
    """Ítem (línea) de una devolución."""

    devolucion = models.ForeignKey(
        Devolucion,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='devolución',
    )
    producto = models.CharField('producto', max_length=200)
    sku = models.CharField('SKU', max_length=50, blank=True)
    cantidad = models.DecimalField('cantidad', max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(
        'precio unitario', max_digits=12, decimal_places=2
    )
    # Lote creado al reingresar al inventario (se llena en la acción completar)
    lote_reingreso = models.ForeignKey(
        'productos.Lote',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='lote de reingreso',
    )

    class Meta:
        verbose_name = 'Ítem de devolución'
        verbose_name_plural = 'Ítems de devolución'

    def __str__(self):
        return f'{self.producto} x {self.cantidad}'

    @property
    def subtotal(self):
        """Subtotal del ítem: cantidad × precio_unitario."""
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        # Hereda la organización de la devolución automáticamente
        if not self.organization_id and self.devolucion_id:
            self.organization = self.devolucion.organization
        super().save(*args, **kwargs)
