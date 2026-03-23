from django.db import models
from apps.pedidos.models import TenantModel


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


class Producto(TenantModel):
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
