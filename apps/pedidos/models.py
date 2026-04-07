from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class TenantModel(models.Model):
    """Clase base para todos los modelos que pertenecen a una organización."""
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.PROTECT,
        verbose_name='organización',
    )

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    """Modelo base para soportar borrado lógico / soft delete."""
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def soft_delete(self, user=None):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by = user
        self.save()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()

    class Meta:
        abstract = True

class Cliente(TenantModel, SoftDeleteModel):
    """Cliente de la organización."""
    nombre    = models.CharField('nombre', max_length=200)
    contacto  = models.CharField('persona de contacto', max_length=200, blank=True)
    telefono  = models.CharField('teléfono', max_length=50, blank=True)
    email     = models.EmailField('email', blank=True)
    direccion = models.TextField('dirección', blank=True)
    lista_precio = models.ForeignKey(
        'configuracion.ListaPrecio',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='lista de precios',
        related_name='clientes',
    )
    limite_credito = models.DecimalField(
        'límite de crédito', max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='0 = sin límite',
    )
    dias_credito = models.PositiveSmallIntegerField(
        'días de crédito', default=0,
        help_text='0 = pago contado',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nombre']
        # Nombre único por organización
        unique_together = [['organization', 'nombre']]

    def __str__(self):
        return self.nombre

    def puede_eliminarse(self):
        """Un cliente no puede eliminarse si tiene pedidos."""
        return not self.pedido_set.exists()


class Pedido(TenantModel):
    """Pedido de venta."""

    ESTADOS = [
        ('Pendiente',   'Pendiente'),
        ('Confirmado',  'Confirmado'),
        ('En Proceso',  'En Proceso'),
        ('Entregado',   'Entregado'),
        ('Cancelado',   'Cancelado'),
    ]

    ESTADOS_DESPACHO = [
        ('Pendiente Despacho', 'Pendiente Despacho'),
        ('Programado',         'Programado'),
        ('En Tránsito',        'En Tránsito'),
        ('Despachado',         'Despachado'),
        ('Devuelto',           'Devuelto'),
    ]

    # Estados terminales que no pueden cambiarse
    ESTADOS_TERMINALES = ['Entregado', 'Cancelado']

    numero          = models.CharField('N° pedido', max_length=20)
    fecha_pedido    = models.DateField('fecha del pedido', db_index=True)
    fecha_entrega   = models.DateField('fecha de entrega estimada', null=True, blank=True, db_index=True)
    cliente         = models.ForeignKey(Cliente, on_delete=models.PROTECT, verbose_name='cliente')
    vendedor        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pedidos_vendedor',
        verbose_name='vendedor',
    )
    estado          = models.CharField('estado', max_length=20, choices=ESTADOS, default='Pendiente', db_index=True)
    estado_despacho = models.CharField(
        'estado de despacho', max_length=30,
        choices=ESTADOS_DESPACHO, default='Pendiente Despacho', db_index=True
    )
    ref_competencia = models.CharField('referencia competencia', max_length=500, blank=True)
    observaciones   = models.TextField('observaciones', blank=True)
    metodo_pago     = models.ForeignKey(
        'configuracion.MetodoPago',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='método de pago',
        related_name='pedidos',
    )
    zona_despacho   = models.ForeignKey(
        'configuracion.ZonaDespacho',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='zona de despacho',
        related_name='pedidos',
    )
    lista_precio    = models.ForeignKey(
        'configuracion.ListaPrecio',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='lista de precios aplicada',
        related_name='pedidos',
    )
    subtotal        = models.DecimalField('subtotal', max_digits=12, decimal_places=2, default=0)
    monto_iva       = models.DecimalField('monto IVA', max_digits=12, decimal_places=2, default=0)
    total           = models.DecimalField('total', max_digits=12, decimal_places=2, default=0)
    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pedidos_creados',
        null=True, blank=True,
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-fecha_pedido', '-created_at']
        # Número único por organización
        unique_together = [['organization', 'numero']]

    def __str__(self):
        return f'{self.numero} — {self.cliente}'

    def recalcular_total(self):
        """Recalcula subtotal, IVA y total sumando todos los items."""
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        resultado = self.items.aggregate(
            subtotal_calc=Sum(
                ExpressionWrapper(F('cantidad') * F('precio'), output_field=DecimalField())
            ),
            iva_calc=Sum('monto_iva')
        )
        self.subtotal = resultado['subtotal_calc'] or 0
        self.monto_iva = resultado['iva_calc'] or 0
        self.total = self.subtotal + self.monto_iva
        self.save(update_fields=['subtotal', 'monto_iva', 'total'])

    def puede_cambiar_estado(self):
        """Los pedidos en estado terminal no pueden cambiar."""
        return self.estado not in self.ESTADOS_TERMINALES

    def puede_eliminarse(self):
        """Solo los pedidos en Pendiente pueden eliminarse."""
        return self.estado == 'Pendiente'

    @property
    def monto_facturado(self):
        """Suma de montos de todas las facturas asociadas."""
        from django.db.models import Sum
        return self.facturas.aggregate(total=Sum('monto'))['total'] or 0

    @property
    def estado_facturacion(self):
        """Estado de facturación: sin_facturar, parcial, facturado."""
        facturado = self.monto_facturado
        if facturado == 0:
            return 'sin_facturar'
        if facturado < self.total:
            return 'parcial'
        return 'facturado'

    @property
    def tasa_cambio_actual(self):
        from apps.cuotas.models import TasaCambio
        tasa = TasaCambio.objects.filter(organization=self.organization).order_by('-fecha').first()
        return tasa.tasa_bs_por_usd if tasa else 0

    @property
    def total_bs(self):
        tasa = self.tasa_cambio_actual
        if tasa:
            return self.total * tasa
        return 0

    @property
    def monto_facturado_bs(self):
        tasa = self.tasa_cambio_actual
        if tasa:
            return self.monto_facturado * tasa
        return 0


class PedidoItem(TenantModel):
    """Ítem / línea de un pedido."""
    pedido   = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.CharField('producto', max_length=200)
    sku      = models.CharField('SKU', max_length=50, blank=True)
    cantidad = models.DecimalField('cantidad', max_digits=10, decimal_places=2)
    precio   = models.DecimalField('precio unitario', max_digits=12, decimal_places=2)
    exento_iva = models.BooleanField('exento de IVA', default=True)
    monto_iva = models.DecimalField('monto IVA', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ítem del pedido'
        verbose_name_plural = 'Ítems del pedido'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0),
                name='cantidad_positiva'
            ),
            models.CheckConstraint(
                condition=models.Q(precio__gte=0),
                name='precio_positivo'
            ),
        ]

    def __str__(self):
        return f'{self.producto} x {self.cantidad}'

    @property
    def subtotal(self):
        return self.cantidad * self.precio

    def save(self, *args, **kwargs):
        if not self.organization_id and self.pedido_id:
            self.organization = self.pedido.organization
        super().save(*args, **kwargs)


class Factura(TenantModel):
    """Factura externa asociada a un pedido."""
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='facturas')
    numero_factura = models.CharField('número de factura', max_length=50)
    fecha_factura = models.DateField('fecha de factura')
    monto = models.DecimalField('monto', max_digits=12, decimal_places=2)
    observaciones = models.TextField('observaciones', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='facturas_creadas',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturas'
        ordering = ['-fecha_factura']

    def __str__(self):
        return f'{self.numero_factura} — ${self.monto}'

    @property
    def monto_bs(self):
        tasa = self.pedido.tasa_cambio_actual
        if tasa:
            return self.monto * tasa
        return 0

    def save(self, *args, **kwargs):
        if not self.organization_id and self.pedido_id:
            self.organization = self.pedido.organization
        super().save(*args, **kwargs)


class PedidoLog(TenantModel):
    """Log de auditoría para cambios en pedidos."""
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='logs')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    accion = models.CharField(max_length=50)
    detalle = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de pedido'
        verbose_name_plural = 'Logs de pedidos'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.pedido.numero} — {self.accion}'

    def save(self, *args, **kwargs):
        if not self.organization_id and self.pedido_id:
            self.organization = self.pedido.organization
        super().save(*args, **kwargs)


class PedidoEstadoHistorial(TenantModel):
    """Registro de tiempo exacto y usuario que cambia un estado del pedido."""
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='historial_estados')
    estado_anterior = models.CharField('estado anterior', max_length=30)
    estado_nuevo = models.CharField('estado nuevo', max_length=30)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    observaciones = models.TextField('observaciones', blank=True)
    created_at = models.DateTimeField('fecha de cambio', auto_now_add=True)

    class Meta:
        verbose_name = 'Historial de estado'
        verbose_name_plural = 'Historial de estados'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.pedido.numero}: {self.estado_anterior} -> {self.estado_nuevo}'

    def save(self, *args, **kwargs):
        if not self.organization_id and self.pedido_id:
            self.organization = self.pedido.organization
        super().save(*args, **kwargs)
