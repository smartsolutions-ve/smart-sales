"""Vistas del dashboard gerencial con KPIs."""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from decimal import Decimal
import datetime

from apps.accounts.decorators import role_required
from .models import Pedido


@login_required
@role_required('gerente', 'superadmin')
def index(request):
    org = request.org
    periodo = request.GET.get('periodo', 'mes')

    hoy = timezone.now().date()
    if periodo == 'mes':
        inicio = hoy.replace(day=1)
    elif periodo == 'mes_anterior':
        primer_dia_mes_actual = hoy.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_mes_actual - datetime.timedelta(days=1)
        inicio = ultimo_dia_mes_anterior.replace(day=1)
    elif periodo == 'tres_meses':
        inicio = (hoy - datetime.timedelta(days=90))
    elif periodo == 'anio':
        inicio = hoy.replace(month=1, day=1)
    else:  # todo
        inicio = None

    pedidos_base = Pedido.objects.filter(organization=org).exclude(estado='Cancelado')
    if inicio:
        pedidos_base = pedidos_base.filter(fecha_pedido__gte=inicio)

    ventas_totales = pedidos_base.aggregate(total=Sum('total'))['total'] or Decimal('0')
    pedidos_activos = Pedido.objects.filter(
        organization=org,
        estado__in=['Confirmado', 'En Proceso']
    ).count()
    pendientes_despacho = Pedido.objects.filter(
        organization=org,
        estado_despacho='Pendiente Despacho',
    ).exclude(estado='Cancelado').count()

    total_no_cancelados = Pedido.objects.filter(organization=org).exclude(estado='Cancelado').count()
    entregados = Pedido.objects.filter(organization=org, estado='Entregado').count()
    tasa_cumplimiento = (
        round((entregados / total_no_cancelados) * 100) if total_no_cancelados > 0 else 0
    )

    # Pedidos urgentes (fecha_entrega en los próximos 3 días)
    hoy_plus3 = hoy + datetime.timedelta(days=3)
    pedidos_urgentes = (
        Pedido.objects
        .filter(organization=org, fecha_entrega__lte=hoy_plus3, fecha_entrega__gte=hoy)
        .exclude(estado__in=['Entregado', 'Cancelado'])
        .select_related('cliente', 'vendedor')
        .order_by('fecha_entrega')[:10]
    )

    context = {
        'ventas_totales': ventas_totales,
        'pedidos_activos': pedidos_activos,
        'pendientes_despacho': pendientes_despacho,
        'tasa_cumplimiento': tasa_cumplimiento,
        'pedidos_urgentes': pedidos_urgentes,
        'periodo': periodo,
    }
    return render(request, 'dashboard/index.html', context)
