from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.accounts.models import Organization
from .models import ConfiguracionEmpresa, UnidadMedida, ListaPrecio, MetodoPago


@receiver(post_save, sender=Organization)
def crear_configuracion_inicial(sender, instance, created, **kwargs):
    """
    Al crear una nueva organización, auto-crear su configuración con valores
    razonables para Venezuela. El gerente puede modificarlos después.
    """
    if not created:
        return

    ConfiguracionEmpresa.objects.create(
        organization=instance,
        nombre_comercial=instance.name,
        moneda_principal='USD',
        zona_horaria='America/Caracas',
    )

    unidades_iniciales = [
        {'nombre': 'Unidad',    'simbolo': 'und', 'tipo': 'CANTIDAD', 'es_base': True},
        {'nombre': 'Caja',      'simbolo': 'cja', 'tipo': 'CANTIDAD', 'factor_conversion': '12'},
        {'nombre': 'Kilogramo', 'simbolo': 'kg',  'tipo': 'PESO',     'es_base': True},
        {'nombre': 'Gramo',     'simbolo': 'g',   'tipo': 'PESO',     'factor_conversion': '0.001'},
        {'nombre': 'Litro',     'simbolo': 'L',   'tipo': 'VOLUMEN',  'es_base': True},
        {'nombre': 'Metro',     'simbolo': 'm',   'tipo': 'LONGITUD', 'es_base': True},
    ]
    for u in unidades_iniciales:
        UnidadMedida.objects.create(organization=instance, **u)

    ListaPrecio.objects.create(
        organization=instance,
        nombre='Precio al público',
        codigo='A',
        descuento_porcentaje=0,
        es_default=True,
    )

    MetodoPago.objects.create(organization=instance, nombre='Efectivo',         tipo='CONTADO')
    MetodoPago.objects.create(organization=instance, nombre='Transferencia',    tipo='TRANSFERENCIA')
    MetodoPago.objects.create(organization=instance, nombre='Crédito 30 días',  tipo='CREDITO', dias_credito=30)
