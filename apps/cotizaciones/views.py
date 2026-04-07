"""Vistas CRUD del módulo de cotizaciones."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from apps.pedidos.models import Cliente

from .models import Cotizacion, CotizacionItem
from .utils import generar_numero_cotizacion


def _get_cotizacion_or_404(pk, org):
    return get_object_or_404(Cotizacion, pk=pk, organization=org)


def _cotizacion_form_ctx(request):
    """Contexto base para el formulario de cotización."""
    from apps.configuracion.models import MetodoPago, ZonaDespacho

    if not request.org:
        return {
            'clientes': Cliente.objects.none(),
            'vendedores': User.objects.none(),
            'estados': Cotizacion.ESTADOS,
            'metodos_pago': MetodoPago.objects.none(),
            'zonas_despacho': ZonaDespacho.objects.none(),
        }
    return {
        'clientes': Cliente.objects.filter(organization=request.org, is_deleted=False).order_by('nombre'),
        'vendedores': request.org.user_set.filter(role__in=['gerente', 'vendedor'], is_active=True),
        'estados': Cotizacion.ESTADOS,
        'metodos_pago': MetodoPago.objects.filter(organization=request.org, activa=True).order_by('nombre'),
        'zonas_despacho': ZonaDespacho.objects.filter(organization=request.org, activa=True).order_by('nombre'),
    }


def _filtrar_cotizaciones(request):
    """Aplica filtros a la lista de cotizaciones y retorna queryset + contexto."""
    from django.db.models import Q as DQ

    q = request.GET.get('q', '')
    estado = request.GET.get('estado', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')

    cotizaciones = (
        Cotizacion.objects
        .filter(organization=request.org)
        .select_related('cliente', 'vendedor')
        .order_by('-fecha', '-created_at')
    )

    if q:
        cotizaciones = cotizaciones.filter(
            DQ(numero__icontains=q) |
            DQ(cliente__nombre__icontains=q) |
            DQ(vendedor__first_name__icontains=q) |
            DQ(vendedor__last_name__icontains=q)
        )
    if estado:
        cotizaciones = cotizaciones.filter(estado=estado)
    if desde:
        cotizaciones = cotizaciones.filter(fecha__gte=desde)
    if hasta:
        cotizaciones = cotizaciones.filter(fecha__lte=hasta)

    # Vendedor solo ve sus propias cotizaciones
    if request.user.is_vendedor:
        cotizaciones = cotizaciones.filter(vendedor=request.user)

    return cotizaciones, {
        'q': q,
        'estado_filtro': estado,
        'desde': desde,
        'hasta': hasta,
        'estados': Cotizacion.ESTADOS,
    }


@login_required
@role_required('gerente', 'superadmin', 'supervisor', 'vendedor')
def lista(request):
    """Lista de cotizaciones con filtros."""
    cotizaciones, filtros = _filtrar_cotizaciones(request)
    context = {'cotizaciones': cotizaciones, **filtros}
    return render(request, 'cotizaciones/lista.html', context)


@login_required
@role_required('gerente', 'superadmin', 'supervisor', 'vendedor')
def crear(request):
    """Crear nueva cotización."""
    if request.method == 'POST':
        return _guardar_cotizacion(request, cotizacion=None)
    return render(request, 'cotizaciones/form.html', _cotizacion_form_ctx(request))


@login_required
@role_required('gerente', 'superadmin', 'supervisor', 'vendedor')
def detalle(request, pk):
    """Ver detalle de una cotización."""
    cotizacion = (
        Cotizacion.objects
        .filter(pk=pk, organization=request.org)
        .select_related('cliente', 'vendedor', 'pedido_generado', 'metodo_pago', 'zona_despacho')
        .prefetch_related('items')
        .first()
    )
    if not cotizacion:
        from django.http import Http404
        raise Http404

    # Obtener condiciones: usar las de la cotización o las de ConfiguracionEmpresa
    condiciones = cotizacion.condiciones
    if not condiciones and request.org:
        try:
            condiciones = request.org.configuracion.terminos_condiciones
        except Exception:
            condiciones = ''

    return render(request, 'cotizaciones/detalle.html', {
        'cotizacion': cotizacion,
        'condiciones': condiciones,
    })


@login_required
@role_required('gerente', 'superadmin', 'supervisor')
@require_http_methods(['GET', 'POST'])
def editar(request, pk):
    """Editar cotización (solo si puede_editarse)."""
    cotizacion = _get_cotizacion_or_404(pk, request.org)
    if not cotizacion.puede_editarse():
        messages.error(request, 'Esta cotización no puede editarse en su estado actual.')
        return redirect('cotizaciones:detalle', pk=pk)

    if request.method == 'POST':
        return _guardar_cotizacion(request, cotizacion=cotizacion)

    return render(request, 'cotizaciones/form.html', {
        **_cotizacion_form_ctx(request),
        'cotizacion': cotizacion,
    })


@login_required
@role_required('gerente', 'superadmin', 'supervisor')
@require_POST
def eliminar(request, pk):
    """Eliminar cotización (solo si está en Borrador)."""
    cotizacion = _get_cotizacion_or_404(pk, request.org)
    if cotizacion.estado != 'Borrador':
        messages.error(request, 'Solo se pueden eliminar cotizaciones en estado Borrador.')
        return redirect('cotizaciones:detalle', pk=pk)
    numero = cotizacion.numero
    cotizacion.delete()
    messages.success(request, f'Cotización {numero} eliminada.')
    return redirect('cotizaciones:lista')


@login_required
@role_required('gerente', 'superadmin', 'supervisor')
@require_POST
def cambiar_estado(request, pk):
    """Cambia el estado de una cotización según transiciones permitidas."""
    cotizacion = _get_cotizacion_or_404(pk, request.org)
    nuevo_estado = request.POST.get('estado')

    # Mapa de transiciones válidas
    TRANSICIONES_VALIDAS = {
        'Borrador':  ['Enviada'],
        'Enviada':   ['Aceptada', 'Rechazada'],
        'Aceptada':  ['Vencida'],
    }

    estados_permitidos = TRANSICIONES_VALIDAS.get(cotizacion.estado, [])
    estados_validos = [e[0] for e in Cotizacion.ESTADOS]

    if cotizacion.estado in Cotizacion.ESTADOS_TERMINALES:
        messages.error(request, 'Esta cotización está en estado terminal y no puede cambiar.')
    elif nuevo_estado not in estados_validos:
        messages.error(request, 'Estado no válido.')
    elif nuevo_estado not in estados_permitidos:
        messages.error(request, f'No se puede pasar de {cotizacion.estado} a {nuevo_estado}.')
    else:
        cotizacion.estado = nuevo_estado
        cotizacion.save(update_fields=['estado'])
        messages.success(request, f'Estado actualizado a {nuevo_estado}.')

    return redirect('cotizaciones:detalle', pk=pk)


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def convertir_a_pedido(request, pk):
    """Convierte una cotización Aceptada en un Pedido."""
    from django.db import transaction

    cotizacion = _get_cotizacion_or_404(pk, request.org)

    if not cotizacion.puede_convertirse():
        messages.error(
            request,
            'Solo cotizaciones Aceptadas sin pedido asociado pueden convertirse.',
        )
        return redirect('cotizaciones:detalle', pk=pk)

    from apps.pedidos.services import PedidoService

    items_data = [
        {
            'producto': item.producto,
            'sku': item.sku,
            'cantidad': float(item.cantidad),
            'precio': float(item.precio),
        }
        for item in cotizacion.items.all()
    ]

    with transaction.atomic():
        pedido = PedidoService.guardar_pedido(
            organization=request.org,
            user=request.user,
            cliente=cotizacion.cliente,
            vendedor=cotizacion.vendedor,
            fecha_pedido=date.today(),
            items_data=items_data,
            metodo_pago=cotizacion.metodo_pago,
            zona_despacho=cotizacion.zona_despacho,
        )
        cotizacion.estado = 'Convertida'
        cotizacion.pedido_generado = pedido
        cotizacion.save(update_fields=['estado', 'pedido_generado'])

    messages.success(
        request,
        f'Pedido {pedido.numero} creado desde cotización {cotizacion.numero}.',
    )
    return redirect('pedidos:detalle', pk=pedido.pk)


@login_required
@role_required('gerente', 'superadmin')
def detalle_pdf(request, pk):
    """Genera PDF de la cotización usando weasyprint."""
    from django.utils import timezone
    from django.http import Http404
    from weasyprint import HTML

    cotizacion = (
        Cotizacion.objects
        .filter(pk=pk, organization=request.org)
        .select_related('cliente', 'vendedor', 'metodo_pago', 'zona_despacho')
        .prefetch_related('items')
        .first()
    )
    if not cotizacion:
        raise Http404

    # Obtener datos de configuración de la empresa
    config = None
    condiciones = cotizacion.condiciones
    try:
        config = request.org.configuracion
        if not condiciones:
            condiciones = config.terminos_condiciones
    except Exception:
        pass

    html_string = render(request, 'cotizaciones/detalle_pdf.html', {
        'cotizacion': cotizacion,
        'org': request.org,
        'config': config,
        'condiciones': condiciones,
        'fecha_generacion': timezone.now().strftime('%d/%m/%Y %H:%M'),
    }).content.decode('utf-8')

    pdf_file = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="cotizacion_{cotizacion.numero}.pdf"'
    return response


def _guardar_cotizacion(request, cotizacion):
    """Lógica compartida para crear y editar cotizaciones."""
    from django.db import transaction
    from decimal import Decimal

    data = request.POST
    errores = []

    # Soporte para tanto 'cliente_id' (Alpine) como 'cliente' (tests)
    cliente_id = data.get('cliente_id') or data.get('cliente')
    vendedor_id = data.get('vendedor_id') or data.get('vendedor')
    fecha_str = data.get('fecha', '')
    fecha_vencimiento_str = data.get('fecha_vencimiento', '') or None
    observaciones = data.get('observaciones', '')
    condiciones = data.get('condiciones', '')
    metodo_pago_id = data.get('metodo_pago_id', '').strip()
    zona_despacho_id = data.get('zona_despacho_id', '').strip()

    # Obtener cliente
    cliente = None
    if cliente_id:
        cliente = get_object_or_404(Cliente, pk=cliente_id, organization=request.org)
    else:
        errores.append('Selecciona un cliente.')

    # Obtener vendedor
    vendedor = None
    if vendedor_id:
        vendedor = get_object_or_404(User, pk=vendedor_id, organization=request.org)
    else:
        errores.append('Selecciona un vendedor.')

    # Parsear items (mismo formato que pedidos: items[][campo])
    productos = data.getlist('items[][producto]')
    cantidades = data.getlist('items[][cantidad]')
    precios = data.getlist('items[][precio]')
    skus = data.getlist('items[][sku]')

    # Fallback formato formset para tests
    if not productos:
        total_forms = int(data.get('items-TOTAL_FORMS', 0))
        for i in range(total_forms):
            prod = data.get(f'items-{i}-producto', '').strip()
            if prod:
                productos.append(prod)
                cantidades.append(data.get(f'items-{i}-cantidad', '0'))
                precios.append(data.get(f'items-{i}-precio', '0'))
                skus.append(data.get(f'items-{i}-sku', ''))

    items_data = []
    for i, producto in enumerate(productos):
        producto = producto.strip()
        if not producto:
            continue
        try:
            cantidad = float(cantidades[i])
            precio = float(precios[i])
            if cantidad <= 0 or precio < 0:
                raise ValueError
        except (ValueError, IndexError):
            errores.append(f'Item {i + 1}: cantidad debe ser > 0 y precio >= 0.')
            continue
        items_data.append({
            'producto': producto,
            'sku': skus[i] if i < len(skus) else '',
            'cantidad': cantidad,
            'precio': precio,
        })

    if not items_data:
        errores.append('La cotización debe tener al menos un ítem.')

    if errores:
        for e in errores:
            messages.error(request, e)
        ctx = _cotizacion_form_ctx(request)
        ctx['cotizacion'] = cotizacion
        return render(request, 'cotizaciones/form.html', ctx)

    from apps.configuracion.models import MetodoPago, ZonaDespacho
    from apps.productos.models import Producto

    metodo_pago = None
    zona_despacho = None
    if metodo_pago_id and request.org:
        metodo_pago = MetodoPago.objects.filter(pk=metodo_pago_id, organization=request.org).first()
    if zona_despacho_id and request.org:
        zona_despacho = ZonaDespacho.objects.filter(pk=zona_despacho_id, organization=request.org).first()

    es_nueva = cotizacion is None

    with transaction.atomic():
        if es_nueva:
            cotizacion = Cotizacion(
                organization=request.org,
                numero=generar_numero_cotizacion(request.org),
                created_by=request.user,
            )

        cotizacion.cliente = cliente
        cotizacion.vendedor = vendedor
        cotizacion.fecha = fecha_str or date.today()
        cotizacion.fecha_vencimiento = fecha_vencimiento_str
        cotizacion.observaciones = observaciones
        cotizacion.condiciones = condiciones
        cotizacion.metodo_pago = metodo_pago
        cotizacion.zona_despacho = zona_despacho

        # Auto-asignar lista de precios del cliente si no hay una asignada
        if cotizacion.lista_precio is None and cliente and cliente.lista_precio_id:
            cotizacion.lista_precio = cliente.lista_precio

        cotizacion.save()

        # Reemplazar items existentes
        if not es_nueva:
            cotizacion.items.all().delete()

        # Lookups de SKUs para determinar IVA
        skus_lista = [item['sku'] for item in items_data if item.get('sku')]
        productos_db = {
            p.sku: p
            for p in Producto.objects.filter(sku__in=skus_lista, organization=request.org)
        }

        items_a_crear = []
        for item_data in items_data:
            exento = True
            monto_iva = Decimal('0.00')
            if item_data.get('sku') in productos_db:
                prod = productos_db[item_data['sku']]
                exento = prod.exento_iva
            if not exento:
                subtotal_item = Decimal(str(item_data['cantidad'])) * Decimal(str(item_data['precio']))
                monto_iva = subtotal_item * Decimal('0.16')

            items_a_crear.append(CotizacionItem(
                cotizacion=cotizacion,
                organization=request.org,
                exento_iva=exento,
                monto_iva=monto_iva,
                producto=item_data['producto'],
                sku=item_data.get('sku', ''),
                cantidad=item_data['cantidad'],
                precio=item_data['precio'],
            ))

        CotizacionItem.objects.bulk_create(items_a_crear)
        cotizacion.recalcular_total()

    messages.success(request, f'Cotización {cotizacion.numero} guardada correctamente.')
    return redirect('cotizaciones:detalle', pk=cotizacion.pk)
