"""
Vistas del módulo de Devoluciones y Notas de Crédito.

Flujo de estados:
  Pendiente → Aprobada → Completada
  Pendiente → Rechazada
"""
import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.pedidos.models import Cliente, Pedido, PedidoItem

from .models import Devolucion, DevolucionItem


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_devolucion_or_404(pk, org):
    """Obtiene una devolución filtrando por organización."""
    return get_object_or_404(Devolucion, pk=pk, organization=org)


# ── Vistas ─────────────────────────────────────────────────────────────────────

@login_required
@role_required('gerente', 'superadmin')
def lista(request):
    """Lista de devoluciones con filtros por estado, cliente y fechas."""
    devoluciones = (
        Devolucion.objects
        .filter(organization=request.org)
        .select_related('cliente', 'pedido', 'registrado_por')
        .order_by('-fecha', '-created_at')
    )

    # Filtros
    estado = request.GET.get('estado', '')
    cliente_id = request.GET.get('cliente', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')

    if estado:
        devoluciones = devoluciones.filter(estado=estado)
    if cliente_id:
        devoluciones = devoluciones.filter(cliente_id=cliente_id)
    if desde:
        devoluciones = devoluciones.filter(fecha__gte=desde)
    if hasta:
        devoluciones = devoluciones.filter(fecha__lte=hasta)

    clientes = Cliente.objects.filter(
        organization=request.org, is_deleted=False
    ).order_by('nombre')

    ctx = {
        'devoluciones': devoluciones,
        'clientes': clientes,
        'estados': Devolucion.ESTADOS,
        'filtro_estado': estado,
        'filtro_cliente': cliente_id,
        'filtro_desde': desde,
        'filtro_hasta': hasta,
    }
    return render(request, 'devoluciones/lista.html', ctx)


@login_required
@role_required('gerente', 'superadmin')
def crear(request):
    """Crea una nueva devolución con sus ítems."""
    clientes = Cliente.objects.filter(
        organization=request.org, is_deleted=False
    ).order_by('nombre')

    if request.method == 'POST':
        pedido_id = request.POST.get('pedido')
        cliente_id = request.POST.get('cliente')
        motivo = request.POST.get('motivo')
        observaciones = request.POST.get('observaciones', '')
        reingresar = request.POST.get('reingresar_inventario') == 'on'

        # Validaciones básicas
        if not pedido_id or not cliente_id or not motivo:
            messages.error(request, 'Pedido, cliente y motivo son obligatorios.')
            ctx = {
                'clientes': clientes,
                'motivos': Devolucion.MOTIVOS,
                'post': request.POST,
            }
            return render(request, 'devoluciones/form.html', ctx)

        pedido = get_object_or_404(Pedido, pk=pedido_id, organization=request.org)
        cliente = get_object_or_404(Cliente, pk=cliente_id, organization=request.org)

        # Construir ítems desde el POST (formato: items[0][producto], items[0][sku], etc.)
        items_data = _parsear_items_post(request.POST)
        if not items_data:
            messages.error(request, 'Debe incluir al menos un ítem en la devolución.')
            ctx = {
                'clientes': clientes,
                'motivos': Devolucion.MOTIVOS,
                'post': request.POST,
            }
            return render(request, 'devoluciones/form.html', ctx)

        devolucion = Devolucion.objects.create(
            organization=request.org,
            pedido=pedido,
            cliente=cliente,
            fecha=request.POST.get('fecha') or date.today(),
            motivo=motivo,
            estado='Pendiente',
            observaciones=observaciones,
            reingresar_inventario=reingresar,
            registrado_por=request.user,
        )

        for item in items_data:
            DevolucionItem.objects.create(
                organization=request.org,
                devolucion=devolucion,
                producto=item['producto'],
                sku=item.get('sku', ''),
                cantidad=item['cantidad'],
                precio_unitario=item['precio_unitario'],
            )

        devolucion.calcular_monto()
        messages.success(request, f'Devolución DEV-{devolucion.pk} registrada exitosamente.')
        return redirect('devoluciones:detalle', pk=devolucion.pk)

    ctx = {
        'clientes': clientes,
        'motivos': Devolucion.MOTIVOS,
        'today': date.today().isoformat(),
    }
    return render(request, 'devoluciones/form.html', ctx)


def _parsear_items_post(post_data):
    """
    Extrae ítems del POST en formato:
      item_producto_0, item_sku_0, item_cantidad_0, item_precio_0
    Retorna lista de dicts o lista vacía si no hay ítems válidos.
    """
    items = []
    index = 0
    while True:
        producto = post_data.get(f'item_producto_{index}', '').strip()
        if not producto:
            break
        try:
            cantidad = float(post_data.get(f'item_cantidad_{index}', 0))
            precio = float(post_data.get(f'item_precio_{index}', 0))
        except (ValueError, TypeError):
            index += 1
            continue
        if cantidad > 0 and precio >= 0:
            items.append({
                'producto': producto,
                'sku': post_data.get(f'item_sku_{index}', '').strip(),
                'cantidad': cantidad,
                'precio_unitario': precio,
            })
        index += 1
    return items


@login_required
@role_required('gerente', 'superadmin')
def detalle(request, pk):
    """Vista de detalle de una devolución."""
    devolucion = _get_devolucion_or_404(pk, request.org)
    items = devolucion.items.select_related('lote_reingreso').all()
    ctx = {
        'devolucion': devolucion,
        'items': items,
    }
    return render(request, 'devoluciones/detalle.html', ctx)


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def aprobar(request, pk):
    """Aprueba una devolución pendiente."""
    devolucion = _get_devolucion_or_404(pk, request.org)

    if not devolucion.puede_aprobar():
        messages.error(request, 'Esta devolución no puede aprobarse en su estado actual.')
        return redirect('devoluciones:detalle', pk=pk)

    devolucion.estado = 'Aprobada'
    devolucion.aprobado_por = request.user
    devolucion.save(update_fields=['estado', 'aprobado_por', 'updated_at'])

    messages.success(request, f'DEV-{devolucion.pk} aprobada correctamente.')
    return redirect('devoluciones:detalle', pk=pk)


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def completar(request, pk):
    """
    Completa una devolución aprobada.
    Si reingresar_inventario=True, crea un Lote y MovimientoInventario por cada ítem con SKU.
    """
    devolucion = _get_devolucion_or_404(pk, request.org)

    if not devolucion.puede_completar():
        messages.error(request, 'Solo se pueden completar devoluciones aprobadas.')
        return redirect('devoluciones:detalle', pk=pk)

    # Actualizar flag de reingreso si el checkbox se envía en el POST
    reingresar = request.POST.get('reingresar_inventario') == 'on'
    devolucion.reingresar_inventario = reingresar

    if reingresar:
        _reingresar_inventario(devolucion, request.org, request.user)

    devolucion.estado = 'Completada'
    devolucion.save(update_fields=['estado', 'reingresar_inventario', 'updated_at'])

    messages.success(request, f'DEV-{devolucion.pk} completada. Nota de crédito generada.')
    return redirect('devoluciones:detalle', pk=pk)


def _reingresar_inventario(devolucion, org, user):
    """
    Crea Lote y MovimientoInventario para cada ítem con SKU reconocido.
    Los ítems sin SKU o cuyo SKU no existe en el catálogo se omiten.
    """
    from django.utils import timezone

    from apps.productos.models import Lote, MovimientoInventario, Producto

    for item in devolucion.items.all():
        if not item.sku:
            continue
        try:
            producto = Producto.objects.get(sku=item.sku, organization=org)
        except Producto.DoesNotExist:
            continue

        # Fecha de caducidad: 1 año desde hoy como referencia para devoluciones
        fecha_caducidad = timezone.now().date().replace(
            year=timezone.now().date().year + 1
        )

        codigo = f'DEV-{devolucion.pk}-{item.sku}'
        lote = Lote.objects.create(
            producto=producto,
            organization=org,
            codigo_lote=codigo,
            cantidad_inicial=item.cantidad,
            cantidad_disponible=item.cantidad,
            fecha_caducidad=fecha_caducidad,
            is_active=True,
        )

        item.lote_reingreso = lote
        item.save(update_fields=['lote_reingreso'])

        MovimientoInventario.objects.create(
            lote=lote,
            organization=org,
            tipo='ENTRADA',
            cantidad=item.cantidad,
            referencia=f'Devolución DEV-{devolucion.pk}',
            created_by=user,
        )


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def rechazar(request, pk):
    """Rechaza una devolución pendiente. Requiere observaciones."""
    devolucion = _get_devolucion_or_404(pk, request.org)

    if not devolucion.puede_rechazar():
        messages.error(request, 'Esta devolución no puede rechazarse en su estado actual.')
        return redirect('devoluciones:detalle', pk=pk)

    observaciones = request.POST.get('observaciones', '').strip()
    if not observaciones:
        messages.error(request, 'Debe indicar el motivo del rechazo en las observaciones.')
        return redirect('devoluciones:detalle', pk=pk)

    devolucion.estado = 'Rechazada'
    devolucion.observaciones = observaciones
    devolucion.save(update_fields=['estado', 'observaciones', 'updated_at'])

    messages.error(request, f'DEV-{devolucion.pk} rechazada.')
    return redirect('devoluciones:detalle', pk=pk)


@login_required
@role_required('gerente', 'superadmin')
def pedido_items_json(request, pedido_pk):
    """
    Endpoint HTMX: retorna los ítems de un pedido para precargar el formulario.
    Filtra por organización para garantizar el aislamiento de tenant.
    """
    pedido = get_object_or_404(Pedido, pk=pedido_pk, organization=request.org)
    items = list(
        pedido.items.values('producto', 'sku', 'cantidad', 'precio')
    )
    return JsonResponse({'items': items})


@login_required
@role_required('gerente', 'superadmin')
def pedidos_por_cliente_json(request):
    """
    Endpoint HTMX: retorna pedidos de un cliente para el select dinámico del formulario.
    Parámetro GET: cliente_id
    """
    cliente_id = request.GET.get('cliente_id', '')
    if not cliente_id:
        return JsonResponse({'pedidos': []})

    pedidos = (
        Pedido.objects
        .filter(organization=request.org, cliente_id=cliente_id)
        .order_by('-fecha_pedido')
        .values('id', 'numero', 'fecha_pedido', 'total')
    )
    # Convertir fecha a string para serialización JSON
    resultado = []
    for p in pedidos:
        resultado.append({
            'id': p['id'],
            'numero': p['numero'],
            'fecha': str(p['fecha_pedido']),
            'total': str(p['total']),
        })
    return JsonResponse({'pedidos': resultado})
