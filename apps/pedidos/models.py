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
        """Recalcula el total sumando los subtotales de todos los items."""
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        resultado = self.items.aggregate(
            total=Sum(
                ExpressionWrapper(F('cantidad') * F('precio'), output_field=DecimalField())
            )
        )
        self.total = resultado['total'] or 0
        self.save(update_fields=['total'])

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


class PedidoItem(models.Model):
    """Ítem / línea de un pedido."""
    pedido   = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.CharField('producto', max_length=200)
    sku      = models.CharField('SKU', max_length=50, blank=True)
    cantidad = models.DecimalField('cantidad', max_digits=10, decimal_places=2)
    precio   = models.DecimalField('precio unitario', max_digits=12, decimal_places=2)

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


class Factura(models.Model):
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


class PedidoLog(models.Model):
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


class PedidoEstadoHistorial(models.Model):
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
