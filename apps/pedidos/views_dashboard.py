"""Vistas del dashboard gerencial con KPIs."""
import json
import datetime
from decimal import Decimal

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Value
from django.db.models.functions import Coalesce

from apps.accounts.decorators import role_required
from .models import Pedido

MESES_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
            'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

COLORES_CHART = ['#0066FF', '#22C55E', '#F59E0B', '#8B5CF6',
                 '#EF4444', '#06B6D4', '#F97316', '#84CC16']

ESTADO_COLORES = {
    'Pendiente':  '#94a3b8',
    'Confirmado': '#3b82f6',
    'En Proceso': '#f59e0b',
    'Entregado':  '#22c55e',
    'Cancelado':  '#ef4444',
}

ORDEN_EMBUDO = ['Pendiente', 'Confirmado', 'En Proceso', 'Entregado']


def _intervalos_6_meses(hoy):
    """Devuelve lista de (primer_dia, ultimo_dia) para los últimos 6 meses."""
    intervalos = []
    for i in range(5, -1, -1):
        # retroceder i meses desde el mes actual
        month = hoy.month - i
        year  = hoy.year
        while month <= 0:
            month += 12
            year  -= 1
        primer_dia = datetime.date(year, month, 1)
        if month == 12:
            ultimo_dia = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            ultimo_dia = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        intervalos.append((primer_dia, ultimo_dia))
    return intervalos


from apps.cuotas.models import VentaMensual

def _dashboard_vendedor(request, org, hoy, inicio, fin):
    """Dashboard UI especial para el vendedor."""
    mes_actual = hoy.replace(day=1)
    # Metas del mes actual
    metas = VentaMensual.objects.filter(
        organization=org, 
        vendedor=request.user, 
        periodo=mes_actual
    ).aggregate(
        plan_total=Coalesce(Sum('plan_venta_usd'), Value(Decimal('0'))),
        real_total=Coalesce(Sum('real_venta_usd'), Value(Decimal('0')))
    )
    plan_total = metas['plan_total']
    real_total = metas['real_total']
    porcentaje = round((real_total / plan_total) * 100) if plan_total > 0 else 0

    # Pedidos del vendedor
    pedidos_base = Pedido.objects.filter(organization=org, vendedor=request.user)
    
    mis_entregados = pedidos_base.filter(estado='Entregado').count()
    mis_activos = pedidos_base.exclude(estado__in=['Entregado', 'Cancelado']).count()
    
    ventas_mes = pedidos_base.filter(
        fecha_pedido__gte=mes_actual
    ).exclude(estado='Cancelado').aggregate(
        total=Coalesce(Sum('total'), Value(Decimal('0')))
    )['total']
    
    # Próximos a entregar
    hoy_plus7 = hoy + datetime.timedelta(days=7)
    proximos = pedidos_base.filter(
        fecha_entrega__lte=hoy_plus7, 
        fecha_entrega__gte=hoy
    ).exclude(estado__in=['Entregado', 'Cancelado']).order_by('fecha_entrega')[:5]

    context = {
        'plan_total': plan_total,
        'real_total': real_total,
        'porcentaje': porcentaje,
        'mis_entregados': mis_entregados,
        'mis_activos': mis_activos,
        'ventas_mes': ventas_mes,
        'proximos': proximos,
    }
    return render(request, 'dashboard/vendedor.html', context)


def _dashboard_supervisor(request, org, hoy, inicio, fin):
    """Dashboard UI especial para el Supervisor de Ventas."""
    equipo = request.user.vendedores_asignados.all()
    vendedores_ids = [v.id for v in equipo]

    mes_actual = hoy.replace(day=1)
    # Metas del equipo entero
    metas = VentaMensual.objects.filter(
        organization=org, 
        vendedor__in=vendedores_ids, 
        periodo=mes_actual
    ).aggregate(
        plan_total=Coalesce(Sum('plan_venta_usd'), Value(Decimal('0'))),
        real_total=Coalesce(Sum('real_venta_usd'), Value(Decimal('0')))
    )
    plan_total = metas['plan_total']
    real_total = metas['real_total']
    porcentaje = round((real_total / plan_total) * 100) if plan_total > 0 else 0

    pedidos_equipo = Pedido.objects.filter(organization=org, vendedor__in=vendedores_ids)
    activos = pedidos_equipo.exclude(estado__in=['Entregado', 'Cancelado']).count()
    entregados = pedidos_equipo.filter(estado='Entregado').count()

    # Progreso por vendedor
    rendimiento = []
    for vendedor in equipo:
        rend = VentaMensual.objects.filter(
            organization=org, vendedor=vendedor, periodo=mes_actual
        ).aggregate(
            p=Coalesce(Sum('plan_venta_usd'), Value(Decimal('0'))),
            r=Coalesce(Sum('real_venta_usd'), Value(Decimal('0')))
        )
        rend_p = rend['p']
        rend_r = rend['r']
        rend_porc = round((rend_r / rend_p) * 100) if rend_p > 0 else 0
        rendimiento.append({
            'nombre': vendedor.get_full_name() or vendedor.username,
            'plan': rend_p,
            'real': rend_r,
            'porcentaje': rend_porc
        })

    context = {
        'plan_total': plan_total,
        'real_total': real_total,
        'porcentaje': porcentaje,
        'activos': activos,
        'entregados': entregados,
        'rendimiento_equipo': rendimiento,
        'equipo_count': equipo.count(),
    }
    return render(request, 'dashboard/supervisor.html', context)


@login_required
@role_required('gerente', 'superadmin', 'supervisor', 'vendedor')
def index(request):
    org = request.org
    hoy = timezone.now().date()
    periodo = request.GET.get('periodo', 'mes')
    desde_param = request.GET.get('desde', '')
    hasta_param = request.GET.get('hasta', '')
    
    # Custom date range overrides periodo presets
    if desde_param or hasta_param:
        inicio = None
        fin = None
        if desde_param:
            try:
                inicio = datetime.date.fromisoformat(desde_param)
            except ValueError:
                inicio = None
        if hasta_param:
            try:
                fin = datetime.date.fromisoformat(hasta_param)
            except ValueError:
                fin = None
    else:
        fin = None
        if periodo == 'mes':
            inicio = hoy.replace(day=1)
        elif periodo == 'mes_anterior':
            primer_dia_mes_actual   = hoy.replace(day=1)
            ultimo_dia_mes_anterior = primer_dia_mes_actual - datetime.timedelta(days=1)
            inicio = ultimo_dia_mes_anterior.replace(day=1)
        elif periodo == 'tres_meses':
            inicio = hoy - datetime.timedelta(days=90)
        elif periodo == 'anio':
            inicio = hoy.replace(month=1, day=1)
        else:
            inicio = None

    # Routing based on Role
    if request.user.is_vendedor:
        return _dashboard_vendedor(request, org, hoy, inicio, fin)
    if request.user.is_supervisor:
        return _dashboard_supervisor(request, org, hoy, inicio, fin)

    # Lógica original para Gerente / Superadmin
    pedidos_base = Pedido.objects.filter(organization=org).exclude(estado='Cancelado')
    if inicio:
        pedidos_base = pedidos_base.filter(fecha_pedido__gte=inicio)
    if fin:
        pedidos_base = pedidos_base.filter(fecha_pedido__lte=fin)

    # ── KPIs ────────────────────────────────────────────────────────────────
    ventas_totales = pedidos_base.aggregate(
        total=Coalesce(Sum('total'), Value(Decimal('0')))
    )['total']
    pedidos_activos = Pedido.objects.filter(
        organization=org, estado__in=['Confirmado', 'En Proceso']
    ).count()
    pendientes_despacho = Pedido.objects.filter(
        organization=org, estado_despacho='Pendiente Despacho',
    ).exclude(estado='Cancelado').count()

    total_no_cancelados = Pedido.objects.filter(organization=org).exclude(estado='Cancelado').count()
    entregados_total    = Pedido.objects.filter(organization=org, estado='Entregado').count()
    tasa_cumplimiento   = (
        round((entregados_total / total_no_cancelados) * 100) if total_no_cancelados else 0
    )

    hoy_plus3 = hoy + datetime.timedelta(days=3)
    pedidos_urgentes = (
        Pedido.objects
        .filter(organization=org, fecha_entrega__lte=hoy_plus3, fecha_entrega__gte=hoy)
        .exclude(estado__in=['Entregado', 'Cancelado'])
        .select_related('cliente', 'vendedor')
        .order_by('fecha_entrega')[:10]
    )

    # ── Gráfica 1: Ventas por mes (últimos 6 meses) ─────────────────────────
    intervalos = _intervalos_6_meses(hoy)
    vendedor_inicio = intervalos[0][0]
    
    from django.db.models.functions import TruncMonth
    ventas_agregadas = list(
        Pedido.objects
        .filter(organization=org, fecha_pedido__gte=vendedor_inicio)
        .exclude(estado='Cancelado')
        .annotate(mes=TruncMonth('fecha_pedido'))
        .values('mes', 'vendedor_id')
        .annotate(total=Sum('total'))
    )
    
    dict_ventas_mes = {}
    dict_ventas_vendedor_mes = {}
    for row in ventas_agregadas:
        y, m = row['mes'].year, row['mes'].month
        dict_ventas_mes[(y, m)] = dict_ventas_mes.get((y, m), Decimal('0')) + (row['total'] or Decimal('0'))
        dict_ventas_vendedor_mes[(y, m, row['vendedor_id'])] = row['total'] or Decimal('0')

    meses_labels = [f"{MESES_ES[p.month - 1]} {p.year}" for p, _ in intervalos]
    meses_ventas = []
    for primer_dia, _ in intervalos:
        total = dict_ventas_mes.get((primer_dia.year, primer_dia.month), 0)
        meses_ventas.append(float(total))

    # ── Gráfica 2: Pedidos por estado (dona) ────────────────────────────────
    estados_qs = list(Pedido.objects.filter(organization=org)
                       .values('estado').annotate(total=Count('id')).order_by('estado'))
    estado_dict = {e['estado']: e['total'] for e in estados_qs}
    
    estados_labels  = [e['estado'] for e in estados_qs]
    estados_data    = [e['total'] for e in estados_qs]
    estados_colores = [ESTADO_COLORES.get(e, '#64748b') for e in estados_labels]

    # ── Gráfica 3: Top 5 vendedores del período (barras) ────────────────────
    top_vendedores_qs = (
        pedidos_base
        .values('vendedor__first_name', 'vendedor__last_name', 'vendedor__username')
        .annotate(total_ventas=Sum('total'), num_pedidos=Count('id'))
        .order_by('-total_ventas')[:5]
    )
    top_vendedores_labels = []
    top_vendedores_data   = []
    for v in top_vendedores_qs:
        nombre = f"{v['vendedor__first_name']} {v['vendedor__last_name']}".strip()
        top_vendedores_labels.append(nombre or v['vendedor__username'])
        top_vendedores_data.append(float(v['total_ventas'] or 0))

    # ── Gráfica 4: Embudo de estados (barras horizontales ordenadas) ─────────
    embudo_labels  = []
    embudo_data    = []
    embudo_colores = []
    for estado in ORDEN_EMBUDO:
        count = estado_dict.get(estado, 0)
        embudo_labels.append(estado)
        embudo_data.append(count)
        embudo_colores.append(ESTADO_COLORES.get(estado, '#64748b'))

    # ── Gráfica 5: Top 10 clientes por ventas (período) ─────────────────────
    top_clientes_qs = (
        pedidos_base
        .filter(cliente__isnull=False)
        .values('cliente__nombre')
        .annotate(total_ventas=Sum('total'))
        .order_by('-total_ventas')[:10]
    )
    top_clientes_labels = [c['cliente__nombre'] for c in top_clientes_qs]
    top_clientes_data   = [float(c['total_ventas'] or 0) for c in top_clientes_qs]

    # ── Gráfica 6: Ventas por vendedor por mes (líneas múltiples) ────────────
    vendedor_ids = list(set([k[2] for k in dict_ventas_vendedor_mes.keys()]))

    from django.contrib.auth import get_user_model
    User = get_user_model()
    vendedores_activos = list(User.objects.filter(pk__in=vendedor_ids).order_by('first_name')[:6])

    datasets_vendedores_mes = []
    for idx, user in enumerate(vendedores_activos):
        nombre = user.get_full_name() or user.username
        data   = []
        for primer_dia, _ in intervalos:
            total = dict_ventas_vendedor_mes.get((primer_dia.year, primer_dia.month, user.id), 0)
            data.append(float(total))
        datasets_vendedores_mes.append({
            'label': nombre,
            'data': data,
            'color': COLORES_CHART[idx % len(COLORES_CHART)],
        })

    context = {
        'ventas_totales':       ventas_totales,
        'pedidos_activos':      pedidos_activos,
        'pendientes_despacho':  pendientes_despacho,
        'tasa_cumplimiento':    tasa_cumplimiento,
        'pedidos_urgentes':     pedidos_urgentes,
        'periodo':              periodo,
        'desde':                desde_param,
        'hasta':                hasta_param,
        'chart_meses_labels':   json.dumps(meses_labels),
        'chart_meses_ventas':   json.dumps(meses_ventas),
        'chart_estados_labels': json.dumps(estados_labels),
        'chart_estados_data':   json.dumps(estados_data),
        'chart_estados_colores':json.dumps(estados_colores),
        'chart_vendedores_labels': json.dumps(top_vendedores_labels),
        'chart_vendedores_data':   json.dumps(top_vendedores_data),
        'chart_embudo_labels':  json.dumps(embudo_labels),
        'chart_embudo_data':    json.dumps(embudo_data),
        'chart_embudo_colores': json.dumps(embudo_colores),
        'chart_clientes_labels': json.dumps(top_clientes_labels),
        'chart_clientes_data':   json.dumps(top_clientes_data),
        'chart_vendedores_mes':  json.dumps(datasets_vendedores_mes),
        'chart_meses_labels_vm': json.dumps(meses_labels),
    }
    return render(request, 'dashboard/index.html', context)
