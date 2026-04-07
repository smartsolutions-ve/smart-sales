import uuid
from datetime import date
from decimal import Decimal
from django.conf import settings
from django.db import models


class ConfiguracionEmpresa(models.Model):
    """
    Configuración central por organización-tenant.
    Se crea automáticamente al crear una organización (signal post_save).
    Solo existe UNA instancia por organización.
    """

    organization = models.OneToOneField(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='configuracion',
        verbose_name='organización',
    )

    # Datos de la empresa
    nombre_comercial = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nombre comercial',
    )
    rif = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='RIF / NIT',
    )
    direccion_fiscal = models.TextField(
        blank=True,
        verbose_name='Dirección fiscal',
    )
    logo = models.ImageField(
        upload_to='logos/',
        blank=True,
        null=True,
        verbose_name='Logo de la empresa',
    )

    # Moneda y región
    MONEDA_CHOICES = [
        ('USD', 'Dólar estadounidense'),
        ('VES', 'Bolívar venezolano'),
        ('EUR', 'Euro'),
        ('COP', 'Peso colombiano'),
    ]
    moneda_principal = models.CharField(
        max_length=3,
        choices=MONEDA_CHOICES,
        default='USD',
        verbose_name='Moneda principal',
    )
    zona_horaria = models.CharField(
        max_length=50,
        default='America/Caracas',
        verbose_name='Zona horaria',
    )

    # Numeración de documentos
    prefijo_pedido = models.CharField(
        max_length=10,
        default='PED',
        verbose_name='Prefijo de pedido',
    )
    digitos_pedido = models.PositiveSmallIntegerField(
        default=6,
        verbose_name='Dígitos en número de pedido',
        help_text='Ej: 6 → PED-000001',
    )
    siguiente_numero_pedido = models.PositiveIntegerField(
        default=1,
        verbose_name='Siguiente número de pedido',
    )
    prefijo_factura = models.CharField(
        max_length=10,
        default='FAC',
        verbose_name='Prefijo de factura',
    )
    siguiente_numero_factura = models.PositiveIntegerField(
        default=1,
        verbose_name='Siguiente número de factura',
    )
    prefijo_cotizacion = models.CharField(
        max_length=10,
        default='COT',
        verbose_name='Prefijo de cotización',
    )
    siguiente_numero_cotizacion = models.PositiveIntegerField(
        default=1,
        verbose_name='Siguiente número de cotización',
    )

    # IVA
    iva_por_defecto = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('16.00'),
        verbose_name='Tasa de IVA por defecto (%)',
    )

    # Inventario
    METODO_VALORACION_CHOICES = [
        ('FEFO', 'FEFO — Primero en vencer, primero en salir'),
        ('FIFO', 'FIFO — Primero en entrar, primero en salir'),
        ('PROMEDIO', 'Costo promedio ponderado'),
    ]
    metodo_valoracion_inventario = models.CharField(
        max_length=10,
        choices=METODO_VALORACION_CHOICES,
        default='FEFO',
        verbose_name='Método de valoración de inventario',
    )
    permitir_stock_negativo = models.BooleanField(
        default=False,
        verbose_name='Permitir ventas con stock negativo',
    )

    # Políticas de crédito por defecto
    dias_credito_default = models.PositiveSmallIntegerField(
        default=30,
        verbose_name='Días de crédito por defecto',
    )
    limite_credito_default = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Límite de crédito por defecto (0 = sin límite)',
    )

    # Legal
    terminos_condiciones = models.TextField(
        blank=True,
        verbose_name='Términos y condiciones',
        help_text='Aparece al pie de facturas y cotizaciones',
    )
    nota_factura = models.TextField(
        blank=True,
        verbose_name='Nota de factura',
        help_text='Campo libre adicional en facturas',
    )

    class Meta:
        verbose_name = 'Configuración de empresa'
        verbose_name_plural = 'Configuraciones de empresa'

    def __str__(self):
        return f'Configuración — {self.organization}'

    def get_numero_pedido(self) -> str:
        """
        Genera el próximo número de pedido formateado y actualiza el contador.
        Llamar siempre dentro de una transacción atómica (select_for_update).
        """
        numero = str(self.siguiente_numero_pedido).zfill(self.digitos_pedido)
        self.siguiente_numero_pedido += 1
        self.save(update_fields=['siguiente_numero_pedido'])
        return f'{self.prefijo_pedido}-{numero}'


class UnidadMedida(models.Model):
    """
    Unidades de medida configurables por empresa.
    Reemplaza el CharField libre en Producto.unidad_medida.
    """

    TIPO_CHOICES = [
        ('PESO', 'Peso'),
        ('VOLUMEN', 'Volumen'),
        ('LONGITUD', 'Longitud'),
        ('AREA', 'Área'),
        ('CANTIDAD', 'Cantidad'),
        ('TIEMPO', 'Tiempo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        verbose_name='organización',
    )
    nombre = models.CharField(
        max_length=50,
        verbose_name='Nombre',
        help_text='Ej: Kilogramo',
    )
    simbolo = models.CharField(
        max_length=10,
        verbose_name='Símbolo',
        help_text='Ej: kg',
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        verbose_name='Tipo',
    )
    es_base = models.BooleanField(
        default=False,
        verbose_name='Es unidad base del tipo',
        help_text='La unidad base tiene factor_conversion = 1',
    )
    factor_conversion = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal('1.000000'),
        verbose_name='Factor de conversión',
        help_text='Relativo a la unidad base del mismo tipo. Ej: 1 caja = 12 unidades → factor 12',
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        ordering = ['tipo', 'nombre']
        verbose_name = 'Unidad de medida'
        verbose_name_plural = 'Unidades de medida'
        unique_together = [['organization', 'simbolo']]
        indexes = [models.Index(fields=['organization', 'tipo', 'activa'])]

    def __str__(self):
        return f'{self.nombre} ({self.simbolo})'


class ListaPrecio(models.Model):
    """
    Listas de precios múltiples por empresa.
    Ej: Precio A Público, Precio B Mayorista, Precio C Distribuidor.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        verbose_name='organización',
    )
    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre',
        help_text='Ej: Precio Mayorista',
    )
    codigo = models.CharField(
        max_length=5,
        verbose_name='Código',
        help_text='Ej: B',
    )
    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Descuento (%)',
        help_text='Descuento sobre precio base del producto',
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')
    es_default = models.BooleanField(
        default=False,
        verbose_name='Lista por defecto',
        help_text='Se aplica a clientes sin lista asignada',
    )

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Lista de precios'
        verbose_name_plural = 'Listas de precios'
        unique_together = [['organization', 'codigo']]

    def __str__(self):
        return f'{self.nombre} ({self.codigo}) — {self.descuento_porcentaje}% dto.'

    def save(self, *args, **kwargs):
        # Solo una lista puede ser la default por organización
        if self.es_default:
            ListaPrecio.objects.filter(
                organization=self.organization, es_default=True
            ).exclude(pk=self.pk).update(es_default=False)
        super().save(*args, **kwargs)


class MetodoPago(models.Model):
    """Métodos de pago configurables por empresa."""

    TIPO_CHOICES = [
        ('CONTADO', 'Contado (efectivo o equivalente)'),
        ('CREDITO', 'Crédito'),
        ('TRANSFERENCIA', 'Transferencia bancaria'),
        ('CHEQUE', 'Cheque'),
        ('MIXTO', 'Mixto'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        verbose_name='organización',
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    tipo = models.CharField(
        max_length=15,
        choices=TIPO_CHOICES,
        verbose_name='Tipo',
    )
    dias_credito = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Días de crédito',
        help_text='Solo aplica para tipo CREDITO',
    )
    activa = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Método de pago'
        verbose_name_plural = 'Métodos de pago'

    def __str__(self):
        return self.nombre


class ZonaDespacho(models.Model):
    """Zonas geográficas de despacho configurables por empresa."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        verbose_name='organización',
    )
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    costo_base_flete = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Costo base de flete',
    )
    dias_entrega_estimados = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Días de entrega estimados',
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Zona de despacho'
        verbose_name_plural = 'Zonas de despacho'

    def __str__(self):
        return self.nombre


class TasaCambio(models.Model):
    """
    Tasa de cambio manual USD→Bs configurada por el gerente.
    Solo una activa por organización. Se conserva historial.
    """

    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='tasas_cambio',
    )
    tasa = models.DecimalField(
        'Tasa USD/Bs',
        max_digits=12,
        decimal_places=4,
        help_text='1 USD = X Bs. Ej: 36.50',
    )
    fecha = models.DateField(
        'Fecha de vigencia',
        default=date.today,
    )
    activa = models.BooleanField(default=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-created_at']
        verbose_name = 'Tasa de cambio'
        verbose_name_plural = 'Tasas de cambio'

    def __str__(self):
        return f'1 USD = {self.tasa} Bs ({self.fecha})'

    @classmethod
    def activa_para(cls, organization):
        """Retorna la tasa vigente más reciente, o None."""
        return cls.objects.filter(organization=organization, activa=True).first()
