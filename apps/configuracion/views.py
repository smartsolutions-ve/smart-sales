from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import IntegrityError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import View

from .models import ConfiguracionEmpresa, ListaPrecio, MetodoPago, UnidadMedida, ZonaDespacho

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


def _puede_configurar(user):
    return user.role in ('gerente', 'superadmin')


def _htmx_list_success(request, template, context, list_id):
    """Retorna partial lista con headers HTMX para retarget y cierre de modal."""
    response = render(request, template, context)
    response['HX-Trigger'] = 'closeModal'
    response['HX-Retarget'] = f'#{list_id}'
    response['HX-Reswap'] = 'innerHTML'
    return response


class ConfiguracionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista principal de configuración — acceso solo para gerente y superadmin."""

    template_name = 'configuracion/index.html'

    def test_func(self):
        return _puede_configurar(self.request.user)

    def _get_context(self, request):
        org = request.org
        config, _ = ConfiguracionEmpresa.objects.get_or_create(
            organization=org,
            defaults={'nombre_comercial': org.name},
        )
        return {
            'config':   config,
            'tabs':     TABS,
            'unidades': UnidadMedida.objects.filter(organization=org, activa=True),
            'listas':   ListaPrecio.objects.filter(organization=org, activa=True),
            'metodos':  MetodoPago.objects.filter(organization=org, activa=True),
            'zonas':    ZonaDespacho.objects.filter(organization=org, activa=True),
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


# ── Logo ──────────────────────────────────────────────────────────────────────

def logo_upload(request):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()
    if request.method != 'POST':
        return HttpResponseForbidden()

    config = get_object_or_404(ConfiguracionEmpresa, organization=request.org)
    archivo = request.FILES.get('logo')
    if archivo:
        config.logo = archivo
        config.save(update_fields=['logo'])
        return render(request, 'configuracion/_logo_preview.html', {'config': config})

    return render(request, 'configuracion/_logo_preview.html', {'config': config})


# ── Unidades de medida ────────────────────────────────────────────────────────

def _unidades_ctx(org):
    return {'unidades': UnidadMedida.objects.filter(organization=org, activa=True)}


def unidades_crear(request):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        simbolo = request.POST.get('simbolo', '').strip()
        tipo = request.POST.get('tipo', '')
        es_base = request.POST.get('es_base') == 'on'
        factor = request.POST.get('factor_conversion', '1') or '1'

        errores = []
        if not nombre:
            errores.append('El nombre es requerido.')
        if not simbolo:
            errores.append('El símbolo es requerido.')
        if not tipo:
            errores.append('El tipo es requerido.')

        if not errores:
            try:
                UnidadMedida.objects.create(
                    organization=request.org,
                    nombre=nombre,
                    simbolo=simbolo,
                    tipo=tipo,
                    es_base=es_base,
                    factor_conversion=factor,
                )
                return _htmx_list_success(
                    request,
                    'configuracion/_unidades_items.html',
                    _unidades_ctx(request.org),
                    'unidades-lista',
                )
            except IntegrityError:
                errores.append(f'Ya existe una unidad con símbolo "{simbolo}".')

        return render(request, 'configuracion/_unidad_form.html', {
            'errores': errores,
            'post': request.POST,
            'tipos': UnidadMedida.TIPO_CHOICES,
        })

    return render(request, 'configuracion/_unidad_form.html', {
        'tipos': UnidadMedida.TIPO_CHOICES,
    })


def unidades_editar(request, pk):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    unidad = get_object_or_404(UnidadMedida, pk=pk, organization=request.org)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        simbolo = request.POST.get('simbolo', '').strip()
        tipo = request.POST.get('tipo', '')
        es_base = request.POST.get('es_base') == 'on'
        factor = request.POST.get('factor_conversion', '1') or '1'

        errores = []
        if not nombre:
            errores.append('El nombre es requerido.')
        if not simbolo:
            errores.append('El símbolo es requerido.')
        if not tipo:
            errores.append('El tipo es requerido.')

        if not errores:
            try:
                unidad.nombre = nombre
                unidad.simbolo = simbolo
                unidad.tipo = tipo
                unidad.es_base = es_base
                unidad.factor_conversion = factor
                unidad.save()
                return _htmx_list_success(
                    request,
                    'configuracion/_unidades_items.html',
                    _unidades_ctx(request.org),
                    'unidades-lista',
                )
            except IntegrityError:
                errores.append(f'Ya existe una unidad con símbolo "{simbolo}".')

        return render(request, 'configuracion/_unidad_form.html', {
            'errores': errores,
            'unidad': unidad,
            'post': request.POST,
            'tipos': UnidadMedida.TIPO_CHOICES,
        })

    return render(request, 'configuracion/_unidad_form.html', {
        'unidad': unidad,
        'tipos': UnidadMedida.TIPO_CHOICES,
    })


@require_POST
def unidades_eliminar(request, pk):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    unidad = get_object_or_404(UnidadMedida, pk=pk, organization=request.org)
    unidad.activa = False
    unidad.save(update_fields=['activa'])

    response = render(request, 'configuracion/_unidades_items.html', _unidades_ctx(request.org))
    response['HX-Retarget'] = '#unidades-lista'
    response['HX-Reswap'] = 'innerHTML'
    return response


# ── Listas de precios ─────────────────────────────────────────────────────────

def _listas_ctx(org):
    return {'listas': ListaPrecio.objects.filter(organization=org, activa=True)}


def listas_crear(request):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        codigo = request.POST.get('codigo', '').strip().upper()
        descuento = request.POST.get('descuento_porcentaje', '0') or '0'
        es_default = request.POST.get('es_default') == 'on'

        errores = []
        if not nombre:
            errores.append('El nombre es requerido.')
        if not codigo:
            errores.append('El código es requerido.')

        if not errores:
            try:
                ListaPrecio.objects.create(
                    organization=request.org,
                    nombre=nombre,
                    codigo=codigo,
                    descuento_porcentaje=descuento,
                    es_default=es_default,
                )
                return _htmx_list_success(
                    request,
                    'configuracion/_listas_items.html',
                    _listas_ctx(request.org),
                    'listas-lista',
                )
            except IntegrityError:
                errores.append(f'Ya existe una lista con código "{codigo}".')

        return render(request, 'configuracion/_lista_precio_form.html', {
            'errores': errores,
            'post': request.POST,
        })

    return render(request, 'configuracion/_lista_precio_form.html', {})


def listas_editar(request, pk):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    lista = get_object_or_404(ListaPrecio, pk=pk, organization=request.org)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        codigo = request.POST.get('codigo', '').strip().upper()
        descuento = request.POST.get('descuento_porcentaje', '0') or '0'
        es_default = request.POST.get('es_default') == 'on'

        errores = []
        if not nombre:
            errores.append('El nombre es requerido.')
        if not codigo:
            errores.append('El código es requerido.')

        if not errores:
            try:
                lista.nombre = nombre
                lista.codigo = codigo
                lista.descuento_porcentaje = descuento
                lista.es_default = es_default
                lista.save()
                return _htmx_list_success(
                    request,
                    'configuracion/_listas_items.html',
                    _listas_ctx(request.org),
                    'listas-lista',
                )
            except IntegrityError:
                errores.append(f'Ya existe una lista con código "{codigo}".')

        return render(request, 'configuracion/_lista_precio_form.html', {
            'errores': errores,
            'lista': lista,
            'post': request.POST,
        })

    return render(request, 'configuracion/_lista_precio_form.html', {'lista': lista})


@require_POST
def listas_eliminar(request, pk):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    lista = get_object_or_404(ListaPrecio, pk=pk, organization=request.org)
    lista.activa = False
    lista.save(update_fields=['activa'])

    response = render(request, 'configuracion/_listas_items.html', _listas_ctx(request.org))
    response['HX-Retarget'] = '#listas-lista'
    response['HX-Reswap'] = 'innerHTML'
    return response


# ── Métodos de pago ───────────────────────────────────────────────────────────

def _metodos_ctx(org):
    return {'metodos': MetodoPago.objects.filter(organization=org, activa=True)}


def metodos_crear(request):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        tipo = request.POST.get('tipo', '')
        dias_credito = request.POST.get('dias_credito', '0') or '0'

        errores = []
        if not nombre:
            errores.append('El nombre es requerido.')
        if not tipo:
            errores.append('El tipo es requerido.')

        if not errores:
            MetodoPago.objects.create(
                organization=request.org,
                nombre=nombre,
                tipo=tipo,
                dias_credito=dias_credito,
            )
            return _htmx_list_success(
                request,
                'configuracion/_metodos_items.html',
                _metodos_ctx(request.org),
                'metodos-lista',
            )

        return render(request, 'configuracion/_metodo_pago_form.html', {
            'errores': errores,
            'post': request.POST,
            'tipos': MetodoPago.TIPO_CHOICES,
        })

    return render(request, 'configuracion/_metodo_pago_form.html', {
        'tipos': MetodoPago.TIPO_CHOICES,
    })


def metodos_editar(request, pk):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    metodo = get_object_or_404(MetodoPago, pk=pk, organization=request.org)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        tipo = request.POST.get('tipo', '')
        dias_credito = request.POST.get('dias_credito', '0') or '0'

        errores = []
        if not nombre:
            errores.append('El nombre es requerido.')
        if not tipo:
            errores.append('El tipo es requerido.')

        if not errores:
            metodo.nombre = nombre
            metodo.tipo = tipo
            metodo.dias_credito = dias_credito
            metodo.save()
            return _htmx_list_success(
                request,
                'configuracion/_metodos_items.html',
                _metodos_ctx(request.org),
                'metodos-lista',
            )

        return render(request, 'configuracion/_metodo_pago_form.html', {
            'errores': errores,
            'metodo': metodo,
            'post': request.POST,
            'tipos': MetodoPago.TIPO_CHOICES,
        })

    return render(request, 'configuracion/_metodo_pago_form.html', {
        'metodo': metodo,
        'tipos': MetodoPago.TIPO_CHOICES,
    })


@require_POST
def metodos_eliminar(request, pk):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    metodo = get_object_or_404(MetodoPago, pk=pk, organization=request.org)
    metodo.activa = False
    metodo.save(update_fields=['activa'])

    response = render(request, 'configuracion/_metodos_items.html', _metodos_ctx(request.org))
    response['HX-Retarget'] = '#metodos-lista'
    response['HX-Reswap'] = 'innerHTML'
    return response


# ── Zonas de despacho ─────────────────────────────────────────────────────────

def _zonas_ctx(org):
    return {'zonas': ZonaDespacho.objects.filter(organization=org, activa=True)}


def zonas_crear(request):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        costo = request.POST.get('costo_base_flete', '0') or '0'
        dias = request.POST.get('dias_entrega_estimados', '1') or '1'

        errores = []
        if not nombre:
            errores.append('El nombre es requerido.')

        if not errores:
            ZonaDespacho.objects.create(
                organization=request.org,
                nombre=nombre,
                costo_base_flete=costo,
                dias_entrega_estimados=dias,
            )
            return _htmx_list_success(
                request,
                'configuracion/_zonas_items.html',
                _zonas_ctx(request.org),
                'zonas-lista',
            )

        return render(request, 'configuracion/_zona_form.html', {
            'errores': errores,
            'post': request.POST,
        })

    return render(request, 'configuracion/_zona_form.html', {})


def zonas_editar(request, pk):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    zona = get_object_or_404(ZonaDespacho, pk=pk, organization=request.org)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        costo = request.POST.get('costo_base_flete', '0') or '0'
        dias = request.POST.get('dias_entrega_estimados', '1') or '1'

        errores = []
        if not nombre:
            errores.append('El nombre es requerido.')

        if not errores:
            zona.nombre = nombre
            zona.costo_base_flete = costo
            zona.dias_entrega_estimados = dias
            zona.save()
            return _htmx_list_success(
                request,
                'configuracion/_zonas_items.html',
                _zonas_ctx(request.org),
                'zonas-lista',
            )

        return render(request, 'configuracion/_zona_form.html', {
            'errores': errores,
            'zona': zona,
            'post': request.POST,
        })

    return render(request, 'configuracion/_zona_form.html', {'zona': zona})


@require_POST
def zonas_eliminar(request, pk):
    if not _puede_configurar(request.user):
        return HttpResponseForbidden()

    zona = get_object_or_404(ZonaDespacho, pk=pk, organization=request.org)
    zona.activa = False
    zona.save(update_fields=['activa'])

    response = render(request, 'configuracion/_zonas_items.html', _zonas_ctx(request.org))
    response['HX-Retarget'] = '#zonas-lista'
    response['HX-Reswap'] = 'innerHTML'
    return response
