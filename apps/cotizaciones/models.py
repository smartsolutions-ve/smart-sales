"""Modelos del módulo de cotizaciones."""
from datetime import date

from django.conf import settings
from django.db import models
from django.db.models import Sum, F, ExpressionWrapper, DecimalField

from apps.pedidos.models import TenantModel


class Cotizacion(TenantModel):
    """
    Cotización de venta enviada al cliente.
    Puede convertirse a Pedido cuando es aceptada.
    No descuenta stock — solo los pedidos lo hacen.
    """

    ESTADOS = [
        ('Borrador', 'Borrador'),
        ('Enviada', 'Enviada al cliente'),
        ('Aceptada', 'Aceptada'),
        ('Rechazada', 'Rechazada'),
        ('Vencida', 'Vencida'),
        ('Convertida', 'Convertida a Pedido'),
    ]

    # Estados que bloquean edición y conversión
    ESTADOS_TERMINALES = ['Rechazada', 'Vencida', 'Convertida']

    numero = models.CharField('N° cotización', max_length=20)
    fecha = models.DateField('Fecha', default=date.today, db_index=True)
    fecha_vencimiento = models.DateField('Válida hasta', null=True, blank=True)
    cliente = models.ForeignKey(
        'pedidos.Cliente',
        on_delete=models.PROTECT,
        related_name='cotizaciones',
        verbose_name='cliente',
    )
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cotizaciones_vendedor',
        verbose_name='vendedor',
    )
    estado = models.CharField(
        'estado', max_length=15, choices=ESTADOS, default='Borrador', db_index=True
    )
    lista_precio = models.ForeignKey(
        'configuracion.ListaPrecio',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='lista de precios',
        related_name='cotizaciones',
    )
    metodo_pago = models.ForeignKey(
        'configuracion.MetodoPago',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='método de pago',
        related_name='cotizaciones',
    )
    zona_despacho = models.ForeignKey(
        'configuracion.ZonaDespacho',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='zona de despacho',
        related_name='cotizaciones',
    )
    subtotal = models.DecimalField('subtotal', max_digits=12, decimal_places=2, default=0)
    monto_iva = models.DecimalField('monto IVA', max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField('total', max_digits=12, decimal_places=2, default=0)
    observaciones = models.TextField('observaciones', blank=True)
    condiciones = models.TextField(
        'Términos y condiciones',
        blank=True,
        help_text='Si vacío, usa los términos de ConfiguracionEmpresa',
    )
    pedido_generado = models.OneToOneField(
        'pedidos.Pedido',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cotizacion_origen',
        verbose_name='pedido generado',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cotizaciones_creadas',
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cotización'
        verbose_name_plural = 'Cotizaciones'
        ordering = ['-fecha', '-created_at']
        unique_together = [['organization', 'numero']]
        indexes = [
            models.Index(fields=['organization', 'estado']),
            models.Index(fields=['organization', 'fecha']),
        ]

    def __str__(self):
        return f'{self.numero} — {self.cliente}'

    def recalcular_total(self):
        """Recalcula subtotal, IVA y total sumando todos los items."""
        resultado = self.items.aggregate(
            subtotal=Sum(
                ExpressionWrapper(F('cantidad') * F('precio'), output_field=DecimalField())
            ),
            iva=Sum('monto_iva'),
        )
        self.subtotal = resultado['subtotal'] or 0
        self.monto_iva = resultado['iva'] or 0
        self.total = self.subtotal + self.monto_iva
        self.save(update_fields=['subtotal', 'monto_iva', 'total'])

    def puede_convertirse(self):
        """Solo cotizaciones Aceptadas sin pedido generado pueden convertirse."""
        return self.estado == 'Aceptada' and not self.pedido_generado_id

    def puede_editarse(self):
        """Las cotizaciones en estado terminal no pueden editarse."""
        return self.estado not in self.ESTADOS_TERMINALES


class CotizacionItem(TenantModel):
    """Ítem / línea de una cotización."""

    cotizacion = models.ForeignKey(
        Cotizacion, on_delete=models.CASCADE, related_name='items'
    )
    producto = models.CharField('producto', max_length=200)
    sku = models.CharField('SKU', max_length=50, blank=True)
    cantidad = models.DecimalField('cantidad', max_digits=10, decimal_places=2)
    precio = models.DecimalField('precio unitario', max_digits=12, decimal_places=2)
    exento_iva = models.BooleanField('exento de IVA', default=True)
    monto_iva = models.DecimalField('monto IVA', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ítem de cotización'
        verbose_name_plural = 'Ítems de cotización'

    def __str__(self):
        return f'{self.producto} x{self.cantidad}'

    @property
    def subtotal(self):
        return self.cantidad * self.precio

    def save(self, *args, **kwargs):
        # Heredar organización de la cotización padre
        if not self.organization_id and self.cotizacion_id:
            self.organization = self.cotizacion.organization
        super().save(*args, **kwargs)
