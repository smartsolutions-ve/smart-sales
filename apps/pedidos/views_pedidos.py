"""Vistas CRUD de pedidos."""
import csv

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction

from apps.accounts.decorators import role_required
from .models import Pedido, PedidoItem, Cliente
from .utils import generar_numero_pedido


def _get_pedido_or_404(pk, org):
    return get_object_or_404(Pedido, pk=pk, organization=org)


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

    return pedidos, {'q': q, 'estado_filtro': estado, 'desde': desde, 'hasta': hasta, 'estados': Pedido.ESTADOS}


@login_required
@role_required('gerente', 'superadmin')
def lista(request):
    pedidos, filtros = _filtrar_pedidos(request)

    context = {'pedidos': pedidos, **filtros}
    if request.htmx:
        return render(request, 'partials/tabla_pedidos.html', context)
    return render(request, 'pedidos/lista.html', context)


@login_required
@role_required('gerente', 'superadmin')
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
@role_required('gerente', 'superadmin')
@require_http_methods(['GET', 'POST'])
def crear(request):
    if request.method == 'POST':
        return _guardar_pedido(request, pedido=None)

    # request.org es None para superadmin (sin organización)
    if not request.org:
        clientes = Cliente.objects.none()
        vendedores = Cliente.objects.none()  # type: ignore
        from apps.accounts.models import User
        vendedores = User.objects.none()
    else:
        clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
        vendedores = request.org.user_set.filter(role__in=["gerente", "vendedor"], is_active=True)

    context = {
        'clientes': clientes,
        'vendedores': vendedores,
        'estados': Pedido.ESTADOS,
    }
    return render(request, 'pedidos/form.html', context)


@login_required
@role_required('gerente', 'superadmin')
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

    if not request.org:
        from apps.accounts.models import User
        clientes = Cliente.objects.none()
        vendedores = User.objects.none()
    else:
        clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
        vendedores = request.org.user_set.filter(role__in=["gerente", "vendedor"], is_active=True)

    context = {
        'pedido': pedido,
        'clientes': clientes,
        'vendedores': vendedores,
        'estados': Pedido.ESTADOS,
    }
    return render(request, 'pedidos/form.html', context)


@login_required
@role_required('gerente', 'superadmin')
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
        from apps.accounts.models import User
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
        except (ValueError, IndexError):
            errores.append(f'Item {i+1}: cantidad o precio inválido.')
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
        if not request.org:
            clientes = Cliente.objects.none()
            from apps.accounts.models import User
            vendedores = User.objects.none()
        else:
            clientes = Cliente.objects.filter(organization=request.org).order_by('nombre')
            vendedores = request.org.user_set.filter(role__in=["gerente", "vendedor"], is_active=True)
        for e in errores:
            messages.error(request, e)
        return render(request, 'pedidos/form.html', {
            'pedido': pedido,
            'clientes': clientes,
            'vendedores': vendedores,
            'estados': Pedido.ESTADOS,
        })

    es_nuevo = pedido is None

    with transaction.atomic():
        if es_nuevo:
            # Crear nuevo pedido
            pedido = Pedido(
                organization=request.org,
                numero=generar_numero_pedido(request.org),
                created_by=request.user,
            )

        pedido.cliente = cliente
        pedido.vendedor = vendedor
        pedido.fecha_pedido = fecha_pedido
        pedido.fecha_entrega = fecha_entrega
        pedido.estado = estado
        pedido.observaciones = observaciones
        pedido.ref_competencia = ref_competencia
        pedido.save()

        # Reemplazar items
        pedido.items.all().delete()
        for item_data in items_data:
            PedidoItem.objects.create(pedido=pedido, **item_data)

        pedido.recalcular_total()

        # Auditoría
        from .audit import log_pedido
        if es_nuevo:
            log_pedido(pedido, request.user, 'creado', f'Cliente: {cliente}, Total: ${pedido.total}')
        else:
            log_pedido(pedido, request.user, 'editado', f'Cliente: {cliente}, Total: ${pedido.total}')

    messages.success(request, f'Pedido {pedido.numero} guardado correctamente.')
    return redirect('pedidos:detalle', pk=pedido.pk)
