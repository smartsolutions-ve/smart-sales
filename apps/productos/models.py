from django.db import models
from apps.pedidos.models import TenantModel, SoftDeleteModel


class CategoriaProducto(TenantModel):
    """Categoría de producto (ej: Ferretería, Repuestos, etc.)."""
    nombre = models.CharField('nombre', max_length=100)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['nombre']
        unique_together = [['organization', 'nombre']]

    def __str__(self):
        return self.nombre


class Producto(TenantModel, SoftDeleteModel):
    """Producto del catálogo de la organización."""

    nombre     = models.CharField('nombre', max_length=200)
    sku        = models.CharField('SKU / Código', max_length=50, blank=True)
    categoria  = models.ForeignKey(
        CategoriaProducto,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='categoría',
        related_name='productos',
    )
    descripcion = models.TextField('descripción', blank=True)
    precio_base = models.DecimalField(
        'precio base', max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text='Precio sugerido de venta. Puede modificarse en cada pedido.',
    )
    unidad      = models.CharField(
        'unidad de medida', max_length=30, blank=True,
        help_text='Ej: unidad, kg, litro, caja',
    )
    peso_kg     = models.DecimalField(
        'peso por unidad (kg)', max_digits=8, decimal_places=3,
        null=True, blank=True,
    )
    is_active   = models.BooleanField('activo', default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['nombre']
        unique_together = [['organization', 'sku']]

    def __str__(self):
        if self.sku:
            return f'[{self.sku}] {self.nombre}'
        return self.nombre

    @property
    def stock_disponible(self):
        from django.db.models import Sum
        return self.lotes.aggregate(total=Sum('cantidad_disponible'))['total'] or 0


class Lote(models.Model):
    """Lote de inventario para soportar metodología FEFO."""
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='lotes')
    codigo_lote = models.CharField('código de lote', max_length=50)
    fecha_elaboracion = models.DateField('fecha de elaboración', null=True, blank=True)
    fecha_caducidad = models.DateField('fecha de caducidad', db_index=True)
    cantidad_inicial = models.DecimalField('cantidad inicial', max_digits=10, decimal_places=2)
    cantidad_disponible = models.DecimalField('cantidad disponible', max_digits=10, decimal_places=2)
    costo_unitario = models.DecimalField('costo unitario', max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField('activo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lote'
        verbose_name_plural = 'Lotes'
        ordering = ['fecha_caducidad', 'created_at']
        unique_together = [['producto', 'codigo_lote']]

    def __str__(self):
        return f'{self.producto.nombre} - Lote: {self.codigo_lote} (Exp: {self.fecha_caducidad})'

class MovimientoInventario(models.Model):
    """Registro de entradas y salidas de inventario por Lote."""
    TIPO_MOVIMIENTO = [
        ('ENTRADA', 'Entrada / Compra'),
        ('SALIDA', 'Salida / Venta'),
        ('AJUSTE', 'Ajuste de Inventario'),
        ('MERMA', 'Merma / Vencido'),
    ]
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField('tipo', max_length=15, choices=TIPO_MOVIMIENTO)
    cantidad = models.DecimalField('cantidad', max_digits=10, decimal_places=2, help_text='Positivo para entradas, negativo para salidas')
    referencia = models.CharField('documento referencia', max_length=100, blank=True, help_text='Ej: Factura X, Pedido Y')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tipo} - {self.lote} : {self.cantidad}'
