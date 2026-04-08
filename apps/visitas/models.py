"""
Modelos del módulo de Visitas Comerciales.
Registra visitas de vendedores a clientes: presenciales, telefónicas y virtuales.
"""

from django.conf import settings
from django.db import models

from apps.pedidos.models import TenantModel


class VisitaComercial(TenantModel):
    """
    Registro de una visita comercial a un cliente.
    Pertenece a una organización (multi-tenant via TenantModel).
    """

    TIPO_CHOICES = [
        ('presencial', 'Presencial'),
        ('telefonica', 'Telefónica'),
        ('virtual', 'Virtual / Videollamada'),
    ]

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('realizada', 'Realizada'),
        ('cancelada', 'Cancelada'),
    ]

    cliente = models.ForeignKey(
        'pedidos.Cliente',
        on_delete=models.CASCADE,
        related_name='visitas',
        verbose_name='cliente',
    )
    vendedor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='visitas',
        verbose_name='vendedor',
    )
    fecha = models.DateField('fecha de visita')
    tipo = models.CharField(
        'tipo de visita',
        max_length=20,
        choices=TIPO_CHOICES,
        default='presencial',
    )
    estado = models.CharField(
        'estado',
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
    )
    objetivo = models.TextField('objetivo de la visita', blank=True)
    resultado = models.TextField('resultado / notas', blank=True)
    proxima_visita = models.DateField('próxima visita', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha', '-created_at']
        verbose_name = 'Visita Comercial'
        verbose_name_plural = 'Visitas Comerciales'
        indexes = [
            models.Index(fields=['organization', 'fecha']),
            models.Index(fields=['organization', 'vendedor']),
            models.Index(fields=['organization', 'estado']),
        ]

    def __str__(self):
        return f'Visita a {self.cliente} — {self.fecha}'

    def marcar_realizada(self, resultado=''):
        """Cambia el estado a realizada. Acepta resultado opcional."""
        self.estado = 'realizada'
        if resultado:
            self.resultado = resultado
        self.save(update_fields=['estado', 'resultado', 'updated_at'])
