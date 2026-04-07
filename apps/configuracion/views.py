from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View
from django.shortcuts import redirect, render

from .models import ConfiguracionEmpresa, UnidadMedida, ListaPrecio, MetodoPago, ZonaDespacho

TABS = [
    ('general',    'General'),
    ('numeracion', 'Numeración'),
    ('inventario', 'Inventario'),
    ('catalogos',  'Catálogos'),
]

CAMPOS_GENERAL = [
    'nombre_comercial', 'rif', 'direccion_fiscal',
    'moneda_principal', 'iva_por_defecto',
]
CAMPOS_NUMERACION = [
    'prefijo_pedido', 'digitos_pedido', 'siguiente_numero_pedido',
    'prefijo_factura', 'siguiente_numero_factura',
    'prefijo_cotizacion',
]
CAMPOS_INVENTARIO = ['metodo_valoracion_inventario']


class ConfiguracionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista principal de configuración — acceso solo para gerente y superadmin."""

    template_name = 'configuracion/index.html'

    def test_func(self):
        return self.request.user.role in ('gerente', 'superadmin')

    def _get_context(self, request):
        org = request.org
        config, _ = ConfiguracionEmpresa.objects.get_or_create(
            organization=org,
            defaults={'nombre_comercial': org.name},
        )
        return {
            'config':   config,
            'tabs':     TABS,
            'unidades': UnidadMedida.objects.filter(organization=org),
            'listas':   ListaPrecio.objects.filter(organization=org),
            'metodos':  MetodoPago.objects.filter(organization=org),
            'zonas':    ZonaDespacho.objects.filter(organization=org),
        }

    def get(self, request):
        return render(request, self.template_name, self._get_context(request))

    def post(self, request):
        accion = request.POST.get('accion', 'general')
        org = request.org
        config = ConfiguracionEmpresa.objects.get(organization=org)

        if accion == 'general':
            for campo in CAMPOS_GENERAL:
                valor = request.POST.get(campo, '')
                setattr(config, campo, valor)
            config.save(update_fields=CAMPOS_GENERAL)
            messages.success(request, 'Datos generales actualizados.')

        elif accion == 'numeracion':
            for campo in CAMPOS_NUMERACION:
                valor = request.POST.get(campo, '')
                if valor:
                    setattr(config, campo, valor)
            config.save(update_fields=CAMPOS_NUMERACION)
            messages.success(request, 'Numeración actualizada.')

        elif accion == 'inventario':
            config.metodo_valoracion_inventario = request.POST.get(
                'metodo_valoracion_inventario', config.metodo_valoracion_inventario
            )
            config.permitir_stock_negativo = 'permitir_stock_negativo' in request.POST
            config.save(update_fields=['metodo_valoracion_inventario', 'permitir_stock_negativo'])
            messages.success(request, 'Políticas de inventario actualizadas.')

        return redirect('configuracion:index')
