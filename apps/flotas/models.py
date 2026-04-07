from django.db import models
from django.conf import settings
from apps.pedidos.models import TenantModel


class Vehiculo(TenantModel):
    """Vehículo de la flota de la organización."""
    placa = models.CharField('placa', max_length=20)
    marca = models.CharField('marca', max_length=50, blank=True)
    modelo = models.CharField('modelo', max_length=50, blank=True)
    capacidad_kg = models.DecimalField('capacidad (kg)', max_digits=10, decimal_places=2)
    chofer_habitual = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehiculos_chofer',
        verbose_name='chofer habitual',
    )
    is_active = models.BooleanField('activo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vehículo'
        verbose_name_plural = 'Vehículos'
        ordering = ['placa']
        unique_together = [['organization', 'placa']]

    def __str__(self):
        desc = f'{self.placa}'
        if self.marca:
            desc += f' — {self.marca}'
            if self.modelo:
                desc += f' {self.modelo}'
        return desc


class Viaje(TenantModel):
    """Viaje de despacho que agrupa pedidos en un vehículo."""

    ESTADOS = [
        ('Programado', 'Programado'),
        ('En Ruta', 'En Ruta'),
        ('Completado', 'Completado'),
        ('Cancelado', 'Cancelado'),
    ]

    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.PROTECT, verbose_name='vehículo')
    chofer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='viajes_chofer',
        verbose_name='chofer',
    )
    fecha = models.DateField('fecha del viaje')
    estado = models.CharField('estado', max_length=20, choices=ESTADOS, default='Programado')
    km_recorridos = models.DecimalField('km recorridos', max_digits=10, decimal_places=2, null=True, blank=True)
    costo_flete = models.DecimalField('costo de flete', max_digits=12, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField('observaciones', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='viajes_creados',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Viaje'
        verbose_name_plural = 'Viajes'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f'Viaje {self.fecha} — {self.vehiculo.placa}'

    @property
    def peso_total_kg(self):
        from django.db.models import Sum
        return self.detalles.aggregate(total=Sum('peso_estimado_kg'))['total'] or 0

    @property
    def porcentaje_utilizacion(self):
        if self.vehiculo.capacidad_kg:
            return round(float(self.peso_total_kg) / float(self.vehiculo.capacidad_kg) * 100, 1)
        return 0

    @property
    def num_pedidos(self):
        return self.detalles.count()

    def puede_eliminarse(self):
        return self.estado == 'Programado'


class ViajeDetalle(TenantModel):
    """Relación viaje-pedido con peso y orden de entrega."""
    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, related_name='detalles')
    pedido = models.ForeignKey('pedidos.Pedido', on_delete=models.PROTECT, related_name='viaje_detalles')
    peso_estimado_kg = models.DecimalField('peso estimado (kg)', max_digits=10, decimal_places=2)
    orden_entrega = models.PositiveSmallIntegerField('orden de entrega', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Detalle de viaje'
        verbose_name_plural = 'Detalles de viaje'
        unique_together = [['viaje', 'pedido']]
        ordering = ['orden_entrega']

    def __str__(self):
        return f'{self.viaje} → {self.pedido.numero}'

    def clean(self):
        super().clean()
        if self.viaje and self.peso_estimado_kg:
            # Calcular peso actual excluyendo este detalle si se está actualizando
            peso_actual = self.viaje.peso_total_kg
            if self.pk:
                from django.db.models import Sum
                # Restar el peso anterior de este detalle mismo para reemplazarlo con el nuevo
                detalle_db = ViajeDetalle.objects.get(pk=self.pk)
                peso_actual -= detalle_db.peso_estimado_kg
                
            nuevo_peso_total = peso_actual + self.peso_estimado_kg
            capacidad_max = self.viaje.vehiculo.capacidad_kg
            
            if nuevo_peso_total > capacidad_max:
                from django.core.exceptions import ValidationError
                raise ValidationError(f'El vehículo {self.viaje.vehiculo.placa} excede su capacidad máxima de {capacidad_max}kg por {nuevo_peso_total - capacidad_max}kg.')

    def save(self, *args, **kwargs):
        if not self.organization_id and self.viaje_id:
            self.organization = self.viaje.organization
        self.clean()
        super().save(*args, **kwargs)
