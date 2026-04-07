"""Vistas CRUD de pedidos."""
import csv

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from .models import Pedido, PedidoItem, Cliente
from .utils import generar_numero_pedido


def _get_pedido_or_404(pk, org):
    return get_object_or_404(Pedido, pk=pk, organization=org)


def _pedido_form_ctx(request):
    """Contexto base para el formulario de pedido."""
    from apps.configuracion.models import MetodoPago, ZonaDespacho
    if not request.org:
        return {
            'clientes': Cliente.objects.none(),
            'vendedores': User.objects.none(),
            'estados': Pedido.ESTADOS,
            'metodos_pago': MetodoPago.objects.none(),
            'zonas_despacho': ZonaDespacho.objects.none(),
        }
    return {
        'clientes': Cliente.objects.filter(organization=request.org).order_by('nombre'),
        'vendedores': request.org.user_set.filter(role__in=['gerente', 'vendedor'], is_active=True),
        'estados': Pedido.ESTADOS,
        'metodos_pago': MetodoPago.objects.filter(organization=request.org, activa=True).order_by('nombre'),
        'zonas_despacho': ZonaDespacho.objects.filter(organization=request.org, activa=True).order_by('nombre'),
    }


def _filtrar_pedidos(request):
    """Aplica filtros comunes a la lista de pedidos y retorna queryset + contexto."""
    from django.db.models import Q as DQ
    q = request.GET.get('q', '')
    estado = request.GET.get('estado', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')

    pedidos = (
        Pedido.objects
        .filter(organization=request.org)
        .select_related('cliente', 'vendedor')
        .order_by('-fecha_pedido', '-created_at')
    )
    if q:
        pedidos = pedidos.filter(
            DQ(numero__icontains=q) |
            DQ(cliente__nombre__icontains=q) |
            DQ(vendedor__first_name__icontains=q) |
            DQ(vendedor__last_name__icontains=q)
        )
    if estado:
        pedidos = pedidos.filter(estado=estado)
    if desde:
        pedidos = pedidos.filter(fecha_pedido__gte=desde)
    if hasta:
        pedidos = pedidos.filter(fecha_pedido__lte=hasta)

    if request.user.is_vendedor:
        pedidos = pedidos.filter(vendedor=request.user)
    elif request.user.is_supervisor:
        pedidos = pedidos.filter(vendedor__supervisor_asignado=request.user)
    elif request.user.is_facturador:
        pedidos = pedidos.filter(estado__in=['Despachado', 'Entregado'])

    return pedidos, {'q': q, 'estado_filtro': estado, 'desde': desde, 'hasta': hasta, 'estados': Pedido.ESTADOS}


@login_required
@role_required('gerente', 'superadmin', 'supervisor', 'vendedor', 'facturador')
def lista(request):
    pedidos, filtros = _filtrar_pedidos(request)

    context = {'pedidos': pedidos, **filtros}
    if request.htmx:
        return render(request, 'partials/tabla_pedidos.html', context)
    return render(request, 'pedidos/lista.html', context)


@login_required
@role_required('gerente', 'superadmin', 'supervisor', 'vendedor', 'facturador')
def exportar_csv(request):
    """Exportar pedidos filtrados a CSV."""
    pedidos, _ = _filtrar_pedidos(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="pedidos.csv"'
    response.write('\ufeff')  # BOM para Excel

    writer = csv.writer(response)
    writer.writerow(['N° Pedido', 'Fecha', 'Cliente', 'Vendedor', 'Estado', 'Estado Despacho', 'Total', 'Observaciones'])

    for p in pedidos:
        writer.writerow([
            p.numero,
            p.fecha_pedido,
            str(p.cliente),
            p.vendedor.get_full_name() or p.vendedor.username,
            p.estado,
            p.estado_despacho,
            p.total,
            p.observaciones,
        ])

    return response


@login_required
@role_required('gerente', 'superadmin', 'supervisor', 'vendedor', 'facturador')
def exportar_json(request):
    """Exportar pedidos filtrados con sus ítems en formato JSON para integración ERP."""
    from django.http import JsonResponse
    pedidos, _ = _filtrar_pedidos(request)
    
    data = []
    for p in pedidos:
        items = [{
            'producto': item.producto,
            'sku': item.sku,
            'cantidad': float(item.cantidad),
            'precio': float(item.precio),
            'subtotal': float(item.subtotal),
        } for item in p.items.all()]
        
        data.append({
            'numero': p.numero,
            'fecha_pedido': p.fecha_pedido.isoformat() if p.fecha_pedido else None,
            'fecha_entrega': p.fecha_entrega.isoformat() if p.fecha_entrega else None,
            'cliente': p.cliente.nombre,
            'vendedor': p.vendedor.get_full_name() or p.vendedor.username,
            'estado': p.estado,
            'estado_despacho': p.estado_despacho,
            'total': float(p.total),
            'observaciones': p.observaciones,
            'items': items,
        })
        
    return JsonResponse(data, safe=False)


@login_required
@role_required('gerente', 'superadmin', 'supervisor')
def crear(request):
    if request.method == 'POST':
        return _guardar_pedido(request, pedido=None)
    return render(request, 'pedidos/form.html', _pedido_form_ctx(request))


@login_required
@role_required('gerente', 'superadmin', 'supervisor', 'vendedor', 'facturador')
def detalle(request, pk):
    pedido = _get_pedido_or_404(pk, request.org)
    return render(request, 'pedidos/detalle.html', {'pedido': pedido})


@login_required
@role_required('gerente', 'superadmin')
def detalle_pdf(request, pk):
    """Genera PDF del detalle de un pedido."""
    from django.utils import timezone
    from django.http import Http404
    from weasyprint import HTML

    pedido = (
        Pedido.objects
        .filter(pk=pk, organization=request.org)
        .select_related('cliente', 'vendedor')
        .prefetch_related('items')
        .first()
    )
    if not pedido:
        raise Http404
    html_string = render(request, 'pedidos/detalle_pdf.html', {
        'pedido': pedido,
        'org': request.org,
        'fecha_generacion': timezone.now().strftime('%d/%m/%Y %H:%M'),
    }).content.decode('utf-8')

    pdf_file = HTML(string=html_string).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="pedido_{pedido.numero}.pdf"'
    return response


@login_required
@role_required('gerente', 'superadmin')
@require_http_methods(['GET', 'POST'])
def editar(request, pk):
    pedido = _get_pedido_or_404(pk, request.org)
    if request.method == 'POST':
        return _guardar_pedido(request, pedido=pedido)

    return render(request, 'pedidos/form.html', {**_pedido_form_ctx(request), 'pedido': pedido})


@login_required
@role_required('gerente', 'superadmin', 'supervisor')
@require_POST
def eliminar(request, pk):
    pedido = _get_pedido_or_404(pk, request.org)
    if not pedido.puede_eliminarse():
        messages.error(request, 'Solo se pueden eliminar pedidos en estado Pendiente.')
        return redirect('pedidos:detalle', pk=pedido.pk)
    pedido.delete()
    messages.success(request, f'Pedido {pedido.numero} eliminado.')
    return redirect('pedidos:lista')


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def cambiar_estado(request, pk):
    pedido = _get_pedido_or_404(pk, request.org)
    nuevo_estado = request.POST.get('estado')
    estados_validos = [e[0] for e in Pedido.ESTADOS]

    if not pedido.puede_cambiar_estado():
        messages.error(request, 'Este pedido está en estado terminal y no puede cambiar.')
    elif nuevo_estado not in estados_validos:
        messages.error(request, 'Estado no válido.')
    else:
        estado_anterior = pedido.estado
        pedido.estado = nuevo_estado
        # RN-008: Al marcar Entregado, despacho pasa a Despachado
        if nuevo_estado == 'Entregado':
            pedido.estado_despacho = 'Despachado'
        elif nuevo_estado == 'Cancelado':
            if pedido.estado_despacho in ['Programado', 'En Tránsito']:
                pedido.estado_despacho = 'Devuelto'
            elif pedido.estado_despacho != 'Despachado' and pedido.estado_despacho != 'Devuelto':
                pedido.estado_despacho = 'Pendiente Despacho'
        pedido.save(update_fields=['estado', 'estado_despacho'])
        messages.success(request, f'Estado actualizado a {nuevo_estado}.')

        # Auditoría
        from .audit import log_pedido
        log_pedido(pedido, request.user, 'cambio_estado', f'{estado_anterior} → {nuevo_estado}')

        # Notificar al vendedor por email
        from .notifications import notificar_cambio_estado
        notificar_cambio_estado(pedido, estado_anterior, request.user)

    if request.htmx:
        return render(request, 'partials/fila_pedido.html', {'pedido': pedido})
    return redirect('pedidos:lista')


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def cambiar_estado_despacho(request, pk):
    pedido = _get_pedido_or_404(pk, request.org)
    nuevo_estado = request.POST.get('estado_despacho')
    estados_validos = [e[0] for e in Pedido.ESTADOS_DESPACHO]

    if nuevo_estado not in estados_validos:
        messages.error(request, 'Estado de despacho no válido.')
    else:
        estado_anterior = pedido.estado_despacho
        pedido.estado_despacho = nuevo_estado
        pedido.save(update_fields=['estado_despacho'])
        messages.success(request, f'Estado de despacho actualizado a {nuevo_estado}.')

        from .audit import log_pedido
        log_pedido(pedido, request.user, 'cambio_despacho', f'{estado_anterior} → {nuevo_estado}')

    if request.htmx:
        return render(request, 'partials/fila_pedido.html', {'pedido': pedido})
    return redirect('pedidos:lista')


@login_required
@role_required('gerente', 'superadmin')
def clonar(request, pk):
    """Crea un nuevo pedido como copia de uno existente."""
    from django.utils import timezone

    original = _get_pedido_or_404(pk, request.org)

    with transaction.atomic():
        nuevo = Pedido(
            organization=request.org,
            numero=generar_numero_pedido(request.org),
            created_by=request.user,
            cliente=original.cliente,
            vendedor=original.vendedor,
            fecha_pedido=timezone.now().date(),
            observaciones=original.observaciones,
            ref_competencia=original.ref_competencia,
        )
        nuevo.save()

        for item in original.items.all():
            PedidoItem.objects.create(
                pedido=nuevo,
                producto=item.producto,
                sku=item.sku,
                cantidad=item.cantidad,
                precio=item.precio,
            )

        nuevo.recalcular_total()

        from .audit import log_pedido
        log_pedido(nuevo, request.user, 'creado', f'Clonado de pedido {original.numero}')

    messages.success(request, f'Pedido {nuevo.numero} creado como copia de {original.numero}.')
    return redirect('pedidos:detalle', pk=nuevo.pk)


def _guardar_pedido(request, pedido):
    """Lógica compartida para crear y editar pedidos."""
    from django.utils import timezone

    data = request.POST
    errores = []

    # Soportar tanto 'cliente_id' (Alpine) como 'cliente' (formset/tests)
    cliente_id = data.get('cliente_id') or data.get('cliente')
    cliente_nuevo_nombre = data.get('cliente_nuevo_nombre', '').strip()
    # Soportar tanto 'vendedor_id' (Alpine) como 'vendedor' (formset/tests)
    vendedor_id = data.get('vendedor_id') or data.get('vendedor')
    fecha_pedido = data.get('fecha_pedido')
    fecha_entrega = data.get('fecha_entrega') or None
    estado = data.get('estado', 'Pendiente')
    observaciones = data.get('observaciones', '')
    ref_competencia = data.get('ref_competencia', '')
    metodo_pago_id = data.get('metodo_pago_id', '').strip()
    zona_despacho_id = data.get('zona_despacho_id', '').strip()

    # Obtener o crear cliente
    cliente = None
    if cliente_id:
        cliente = get_object_or_404(Cliente, pk=cliente_id, organization=request.org)
    elif cliente_nuevo_nombre:
        cliente, _ = Cliente.objects.get_or_create(
            organization=request.org,
            nombre=cliente_nuevo_nombre,
        )
    else:
        errores.append('Selecciona o escribe un cliente.')

    # Obtener vendedor
    vendedor = None
    if vendedor_id:
        vendedor = get_object_or_404(User, pk=vendedor_id, organization=request.org)
    else:
        errores.append('Selecciona un vendedor.')

    # Parsear items: soportar formato Alpine (items[][producto]) y formset (items-N-producto)
    productos = data.getlist('items[][producto]')
    cantidades = data.getlist('items[][cantidad]')
    precios = data.getlist('items[][precio]')
    skus = data.getlist('items[][sku]')

    # Si no hay items en formato Alpine, intentar formato formset (items-N-campo)
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
            errores.append(f'Item {i+1}: cantidad debe ser > 0 y precio >= 0.')
            continue
        items_data.append({
            'producto': producto,
            'sku': skus[i] if i < len(skus) else '',
            'cantidad': cantidad,
            'precio': precio,
        })

    if not items_data:
        errores.append('El pedido debe tener al menos un ítem.')

    if errores:
        for e in errores:
            messages.error(request, e)
        return render(request, 'pedidos/form.html', {**_pedido_form_ctx(request), 'pedido': pedido})

    from apps.configuracion.models import MetodoPago, ZonaDespacho
    metodo_pago = None
    zona_despacho = None
    if metodo_pago_id and request.org:
        metodo_pago = MetodoPago.objects.filter(pk=metodo_pago_id, organization=request.org).first()
    if zona_despacho_id and request.org:
        zona_despacho = ZonaDespacho.objects.filter(pk=zona_despacho_id, organization=request.org).first()

    from .services import PedidoService
    try:
        pedido = PedidoService.guardar_pedido(
            organization=request.org,
            user=request.user,
            cliente=cliente,
            vendedor=vendedor,
            fecha_pedido=fecha_pedido,
            items_data=items_data,
            fecha_entrega=fecha_entrega,
            estado=estado,
            observaciones=observaciones,
            ref_competencia=ref_competencia,
            pedido_existente=pedido,
            metodo_pago=metodo_pago,
            zona_despacho=zona_despacho,
        )
    except Exception as e:
        messages.error(request, str(e))
        return render(request, 'pedidos/form.html', {**_pedido_form_ctx(request), 'pedido': pedido})

    messages.success(request, f'Pedido {pedido.numero} guardado correctamente.')
    return redirect('pedidos:detalle', pk=pedido.pk)
