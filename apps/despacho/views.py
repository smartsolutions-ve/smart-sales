"""Vistas del módulo de despacho y logística."""
from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import role_required
from apps.pedidos.models import Pedido


@login_required
@role_required('gerente', 'superadmin')
def index(request):
    vendedor_id = request.GET.get('vendedor')
    desde = request.GET.get('desde')
    hasta = request.GET.get('hasta')

    pedidos = (
        Pedido.objects
        .filter(organization=request.org)
        .exclude(estado='Cancelado')
        .select_related('cliente', 'vendedor')
        .order_by('fecha_entrega', '-created_at')
    )
    if vendedor_id:
        pedidos = pedidos.filter(vendedor_id=vendedor_id)
    if desde:
        pedidos = pedidos.filter(fecha_entrega__gte=desde)
    if hasta:
        pedidos = pedidos.filter(fecha_entrega__lte=hasta)

    # Agrupar por estado_despacho para vista tipo Kanban
    columnas = {}
    for estado, label in Pedido.ESTADOS_DESPACHO:
        columnas[estado] = {
            'label': label,
            'pedidos': [p for p in pedidos if p.estado_despacho == estado],
        }

    vendedores = request.org.user_set.filter(role__in=['gerente', 'vendedor'], is_active=True) if request.org else []
    today = timezone.now().date()
    context = {
        'columnas': columnas,
        'vendedores': vendedores,
        'vendedor_filtro': vendedor_id,
        'desde': desde,
        'hasta': hasta,
        'today': today,
    }
    return render(request, 'despacho/index.html', context)


@login_required
@role_required('gerente', 'superadmin')
@require_POST
def cambiar_estado_despacho(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, organization=request.org)
    nuevo_estado = request.POST.get('estado_despacho')
    estados_validos = [e[0] for e in Pedido.ESTADOS_DESPACHO]

    if nuevo_estado in estados_validos:
        pedido.estado_despacho = nuevo_estado
        pedido.save(update_fields=['estado_despacho'])
        messages.success(request, f'Estado de despacho actualizado.')
    else:
        messages.error(request, 'Estado no válido.')

    if request.htmx:
        return render(request, 'partials/tarjeta_despacho.html', {'pedido': pedido, 'today': timezone.now().date()})
    return redirect('despacho:index')
