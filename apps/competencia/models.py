from django.db import models
from django.conf import settings
from apps.pedidos.models import TenantModel, Cliente


class CompetenciaRegistro(TenantModel):
    """Registro de inteligencia de competencia reportado por un vendedor."""
    fecha          = models.DateField('fecha del hallazgo')
    cliente        = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='cliente involucrado',
    )
    vendedor       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name='vendedor',
    )
    producto       = models.CharField('producto', max_length=200)
    competidor     = models.CharField('competidor', max_length=200)
    precio_comp    = models.DecimalField(
        'precio del competidor', max_digits=12, decimal_places=2,
        null=True, blank=True,
    )
    precio_nuestro = models.DecimalField(
        'nuestro precio', max_digits=12, decimal_places=2,
        null=True, blank=True,
    )
    accion_tomada  = models.TextField('acción tomada', blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Registro de competencia'
        verbose_name_plural = 'Registros de competencia'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f'{self.competidor} / {self.producto} — {self.fecha}'

    @property
    def diferencia_precio(self):
        """
        Diferencia entre nuestro precio y el del competidor.
        Positivo = somos más caros.
        Negativo = somos más baratos.
        """
        if self.precio_nuestro is not None and self.precio_comp is not None:
            return self.precio_nuestro - self.precio_comp
        return None

    @property
    def somos_mas_caros(self):
        diff = self.diferencia_precio
        return diff is not None and diff > 0
