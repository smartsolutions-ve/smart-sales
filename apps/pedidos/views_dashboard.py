"""Vistas del dashboard gerencial con KPIs."""
import json
import datetime
from decimal import Decimal

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q

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

    # ── Datos para gráficas ─────────────────────────────────────────────────

    # 1. Ventas por mes (últimos 6 meses)
    MESES_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    meses_labels = []
    meses_ventas = []
    for i in range(5, -1, -1):
        # Primer día del mes i meses atrás
        primer_dia = (hoy.replace(day=1) - datetime.timedelta(days=i * 28)).replace(day=1)
        # Último día del mismo mes
        if primer_dia.month == 12:
            ultimo_dia = primer_dia.replace(year=primer_dia.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            ultimo_dia = primer_dia.replace(month=primer_dia.month + 1, day=1) - datetime.timedelta(days=1)

        total_mes = (
            Pedido.objects
            .filter(organization=org, fecha_pedido__gte=primer_dia, fecha_pedido__lte=ultimo_dia)
            .exclude(estado='Cancelado')
            .aggregate(t=Sum('total'))['t'] or Decimal('0')
        )
        meses_labels.append(f"{MESES_ES[primer_dia.month - 1]} {primer_dia.year}")
        meses_ventas.append(float(total_mes))

    # 2. Pedidos por estado (todos los pedidos de la org)
    estados_qs = (
        Pedido.objects
        .filter(organization=org)
        .values('estado')
        .annotate(total=Count('id'))
        .order_by('estado')
    )
    estados_labels = [e['estado'] for e in estados_qs]
    estados_data = [e['total'] for e in estados_qs]
    ESTADO_COLORES = {
        'Borrador': '#94a3b8',
        'Confirmado': '#3b82f6',
        'En Proceso': '#f59e0b',
        'Despachado': '#8b5cf6',
        'Entregado': '#22c55e',
        'Cancelado': '#ef4444',
    }
    estados_colores = [ESTADO_COLORES.get(e, '#64748b') for e in estados_labels]

    # 3. Top 5 vendedores por ventas (en el período actual)
    top_vendedores_qs = (
        pedidos_base
        .values('vendedor__first_name', 'vendedor__last_name', 'vendedor__username')
        .annotate(total_ventas=Sum('total'), num_pedidos=Count('id'))
        .order_by('-total_ventas')[:5]
    )
    top_vendedores_labels = []
    top_vendedores_data = []
    for v in top_vendedores_qs:
        nombre = f"{v['vendedor__first_name']} {v['vendedor__last_name']}".strip()
        top_vendedores_labels.append(nombre or v['vendedor__username'])
        top_vendedores_data.append(float(v['total_ventas'] or 0))

    context = {
        'ventas_totales': ventas_totales,
        'pedidos_activos': pedidos_activos,
        'pendientes_despacho': pendientes_despacho,
        'tasa_cumplimiento': tasa_cumplimiento,
        'pedidos_urgentes': pedidos_urgentes,
        'periodo': periodo,
        # Chart.js data (JSON)
        'chart_meses_labels': json.dumps(meses_labels),
        'chart_meses_ventas': json.dumps(meses_ventas),
        'chart_estados_labels': json.dumps(estados_labels),
        'chart_estados_data': json.dumps(estados_data),
        'chart_estados_colores': json.dumps(estados_colores),
        'chart_vendedores_labels': json.dumps(top_vendedores_labels),
        'chart_vendedores_data': json.dumps(top_vendedores_data),
    }
    return render(request, 'dashboard/index.html', context)

