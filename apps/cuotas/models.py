from django.db import models
from django.conf import settings
from apps.pedidos.models import TenantModel


class Zona(TenantModel):
    """Zona geográfica de ventas."""
    nombre = models.CharField('nombre', max_length=100)
    codigo = models.CharField('código', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Zona'
        verbose_name_plural = 'Zonas'
        ordering = ['nombre']
        unique_together = [['organization', 'nombre']]

    def __str__(self):
        return self.nombre


class TasaCambio(TenantModel):
    """Tasa de cambio diaria."""
    fecha = models.DateField('fecha')
    tasa_bs_por_usd = models.DecimalField('tasa Bs/USD', max_digits=12, decimal_places=4)
    fuente = models.CharField('fuente', max_length=50, blank=True, help_text='Ej: BCV, paralelo')

    class Meta:
        verbose_name = 'Tasa de cambio'
        verbose_name_plural = 'Tasas de cambio'
        ordering = ['-fecha']
        unique_together = [['organization', 'fecha', 'fuente']]

    def __str__(self):
        return f'{self.fecha} — {self.tasa_bs_por_usd} Bs/USD ({self.fuente})'


class VentaMensual(TenantModel):
    """Registro de venta mensual plan vs real, importado desde Excel."""

    CANALES = [
        ('DIRECTO', 'Directo'),
        ('DISTRIBUCIÓN', 'Distribución'),
    ]

    periodo = models.DateField('periodo', help_text='Primer día del mes')
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ventas_mensuales',
    )
    vendedor_nombre = models.CharField('nombre vendedor', max_length=200)
    producto = models.ForeignKey(
        'productos.Producto', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ventas_mensuales',
    )
    producto_nombre = models.CharField('nombre producto', max_length=200)
    codigo_producto = models.CharField('código producto', max_length=50, blank=True)
    zona = models.ForeignKey(Zona, on_delete=models.SET_NULL, null=True, blank=True)
    zona_nombre = models.CharField('nombre zona', max_length=100, blank=True)
    canal = models.CharField('canal', max_length=30, choices=CANALES, blank=True)
    distribucion = models.CharField('distribución', max_length=200, blank=True)

    # PLAN
    plan_cantidad = models.DecimalField('plan cantidad', max_digits=12, decimal_places=2, default=0)
    plan_precio_usd = models.DecimalField('plan precio USD', max_digits=12, decimal_places=2, default=0)
    plan_venta_usd = models.DecimalField('plan venta USD', max_digits=12, decimal_places=2, default=0)
    plan_costo_usd = models.DecimalField('plan costo USD', max_digits=12, decimal_places=2, default=0)
    plan_margen_usd = models.DecimalField('plan margen USD', max_digits=12, decimal_places=2, default=0)
    plan_flete_usd = models.DecimalField('plan flete USD', max_digits=12, decimal_places=2, default=0)
    plan_gastos_fin_usd = models.DecimalField('plan gastos financieros USD', max_digits=12, decimal_places=2, default=0)
    plan_impuestos_usd = models.DecimalField('plan impuestos USD', max_digits=12, decimal_places=2, default=0)
    plan_logisticos_usd = models.DecimalField('plan logísticos USD', max_digits=12, decimal_places=2, default=0)
    plan_gastos_ventas_usd = models.DecimalField('plan gastos ventas USD', max_digits=12, decimal_places=2, default=0)
    plan_margen_neto_usd = models.DecimalField('plan margen neto USD', max_digits=12, decimal_places=2, default=0)

    # REAL
    real_cantidad = models.DecimalField('real cantidad', max_digits=12, decimal_places=2, default=0)
    real_venta_ves = models.DecimalField('real venta VES', max_digits=18, decimal_places=2, default=0)
    real_venta_usd = models.DecimalField('real venta USD', max_digits=12, decimal_places=2, default=0)
    real_costo_usd = models.DecimalField('real costo USD', max_digits=12, decimal_places=2, default=0)
    real_flete_usd = models.DecimalField('real flete USD', max_digits=12, decimal_places=2, default=0)
    real_gastos_fin_usd = models.DecimalField('real gastos financieros USD', max_digits=12, decimal_places=2, default=0)
    real_impuestos_usd = models.DecimalField('real impuestos USD', max_digits=12, decimal_places=2, default=0)
    real_logisticos_usd = models.DecimalField('real logísticos USD', max_digits=12, decimal_places=2, default=0)
    real_gastos_ventas_usd = models.DecimalField('real gastos ventas USD', max_digits=12, decimal_places=2, default=0)
    real_margen_neto_usd = models.DecimalField('real margen neto USD', max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Venta mensual'
        verbose_name_plural = 'Ventas mensuales'
        ordering = ['-periodo', 'vendedor_nombre']
        indexes = [
            models.Index(fields=['organization', 'periodo']),
            models.Index(fields=['organization', 'zona_nombre']),
            models.Index(fields=['organization', 'vendedor_nombre']),
        ]

    def __str__(self):
        return f'{self.periodo:%Y-%m} — {self.vendedor_nombre} — {self.producto_nombre}'

    @property
    def cumplimiento_cantidad(self):
        if self.plan_cantidad:
            return round(float(self.real_cantidad) / float(self.plan_cantidad) * 100, 1)
        return 0

    @property
    def cumplimiento_venta(self):
        if self.plan_venta_usd:
            return round(float(self.real_venta_usd) / float(self.plan_venta_usd) * 100, 1)
        return 0
