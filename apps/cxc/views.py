"""
Vistas del módulo de Cuentas por Cobrar (CxC).

Lógica principal:
- Deuda activa = suma de pedidos en estados activos - pagos recibidos
- Aging: agrupación de deuda por antigüedad del pedido (fecha_pedido → hoy)
"""
import csv
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.pedidos.models import Cliente, Pedido

from .forms import PagoForm
from .models import Pago

# Estados de pedidos que generan deuda pendiente de cobro
ESTADOS_ACTIVOS = ['Pendiente', 'Confirmado', 'En Proceso', 'Entregado']


def _calcular_tramo_aging(fecha_pedido):
    """
    Devuelve el tramo de aging basado en la antigüedad de un pedido.

    Las claves usan guion bajo para ser accesibles en templates Django.
    Mapeo: t0_30 → 0-30 días, t31_60 → 31-60 días, t61_90 → 61-90 días, t90_mas → +90 días.
    """
    dias = (timezone.now().date() - fecha_pedido).days
    if dias <= 30:
        return 't0_30'
    elif dias <= 60:
        return 't31_60'
    elif dias <= 90:
        return 't61_90'
    return 't90_mas'


def _clientes_con_deuda(org):
    """
    Retorna queryset de clientes con saldo positivo para la organización dada.
    Anota: deuda_pedidos, total_pagado, saldo.

    Se usan subqueries separadas en lugar de un JOIN doble para evitar
    la multiplicación de filas cuando un cliente tiene múltiples pedidos y pagos.
    """
    from django.db.models import OuterRef, Subquery

    deuda_sq = (
        Pedido.objects
        .filter(cliente=OuterRef('pk'), estado__in=ESTADOS_ACTIVOS)
        .values('cliente')
        .annotate(total=Sum('total'))
        .values('total')
    )
    pagos_sq = (
        Pago.objects
        .filter(cliente=OuterRef('pk'), organization=org)
        .values('cliente')
        .annotate(total=Sum('monto'))
        .values('total')
    )

    return (
        Cliente.objects
        .filter(organization=org)
        .annotate(
            deuda_pedidos=Coalesce(Subquery(deuda_sq), Decimal('0')),
            total_pagado=Coalesce(Subquery(pagos_sq), Decimal('0')),
        )
        .annotate(saldo=F('deuda_pedidos') - F('total_pagado'))
        .filter(saldo__gt=0)
        .order_by('-saldo')
    )


def _estado_credito(cliente):
    """
    Devuelve el estado de crédito del cliente en función de su límite.

    Retorna uno de: 'sin_limite', 'ok', 'alerta', 'sobre_limite'
    """
    if not cliente.limite_credito or cliente.limite_credito == 0:
        return 'sin_limite'
    pct = (cliente.saldo / cliente.limite_credito) * 100
    if pct > 100:
        return 'sobre_limite'
    if pct > 80:
        return 'alerta'
    return 'ok'


def _dias_pedido_mas_antiguo(cliente_pk, org):
    """Días transcurridos desde el pedido activo más antiguo del cliente."""
    pedido_antiguo = (
        Pedido.objects
        .filter(organization=org, cliente_id=cliente_pk, estado__in=ESTADOS_ACTIVOS)
        .order_by('fecha_pedido')
        .first()
    )
    if not pedido_antiguo:
        return 0
    return (timezone.now().date() - pedido_antiguo.fecha_pedido).days


@login_required
def dashboard(request):
    """
    Vista principal de CxC.
    Lista de clientes con deuda, KPIs globales y agrupación por estado de crédito.
    """
    clientes_qs = _clientes_con_deuda(request.org)

    # Enriquecer con estado de crédito y días más antiguo
    clientes = []
    total_por_cobrar = Decimal('0')
    clientes_en_alerta = 0
    clientes_sobre_limite = 0

    for c in clientes_qs:
        estado = _estado_credito(c)
        dias_antiguo = _dias_pedido_mas_antiguo(c.pk, request.org)

        # Porcentaje utilizado del límite de crédito
        if c.limite_credito and c.limite_credito > 0:
            pct_limite = min(int((c.saldo / c.limite_credito) * 100), 100)
        else:
            pct_limite = 0

        clientes.append({
            'obj': c,
            'saldo': c.saldo,
            'estado': estado,
            'dias_antiguo': dias_antiguo,
            'pct_limite': pct_limite,
        })

        total_por_cobrar += c.saldo
        if estado == 'alerta':
            clientes_en_alerta += 1
        elif estado == 'sobre_limite':
            clientes_sobre_limite += 1

    context = {
        'clientes': clientes,
        'total_por_cobrar': total_por_cobrar,
        'total_clientes': len(clientes),
        'clientes_en_alerta': clientes_en_alerta,
        'clientes_sobre_limite': clientes_sobre_limite,
    }
    return render(request, 'cxc/dashboard.html', context)


@login_required
def cliente_detalle(request, pk):
    """
    Detalle de CxC de un cliente: pedidos activos con aging y historial de pagos.
    """
    cliente = get_object_or_404(Cliente, pk=pk, organization=request.org)

    # Pedidos activos con tramo de aging calculado
    pedidos_activos = (
        Pedido.objects
        .filter(organization=request.org, cliente=cliente, estado__in=ESTADOS_ACTIVOS)
        .order_by('fecha_pedido')
    )

    pedidos_con_aging = []
    totales_aging = {'t0_30': Decimal('0'), 't31_60': Decimal('0'), 't61_90': Decimal('0'), 't90_mas': Decimal('0')}
    for p in pedidos_activos:
        tramo = _calcular_tramo_aging(p.fecha_pedido)
        dias = (timezone.now().date() - p.fecha_pedido).days
        pedidos_con_aging.append({
            'pedido': p,
            'tramo': tramo,
            'dias': dias,
        })
        totales_aging[tramo] += p.total

    # Totales de deuda
    deuda_pedidos = sum(p['pedido'].total for p in pedidos_con_aging)
    total_pagado = Pago.objects.filter(
        organization=request.org, cliente=cliente
    ).aggregate(total=Coalesce(Sum('monto'), Decimal('0')))['total']
    saldo = deuda_pedidos - total_pagado

    # Historial de pagos
    pagos = Pago.objects.filter(organization=request.org, cliente=cliente)

    # Estado de crédito
    if cliente.limite_credito and cliente.limite_credito > 0:
        pct_limite = min(int((saldo / cliente.limite_credito) * 100), 100)
    else:
        pct_limite = 0

    context = {
        'cliente': cliente,
        'pedidos_con_aging': pedidos_con_aging,
        'totales_aging': totales_aging,
        'deuda_pedidos': deuda_pedidos,
        'total_pagado': total_pagado,
        'saldo': saldo,
        'pagos': pagos,
        'pct_limite': pct_limite,
        'form': PagoForm(),
    }
    return render(request, 'cxc/cliente_detalle.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def registrar_pago(request, pk):
    """
    GET: retorna el formulario de pago en modal (HTMX).
    POST: crea el pago y retorna la lista de pagos actualizada.
    """
    cliente = get_object_or_404(Cliente, pk=pk, organization=request.org)

    if request.method == 'POST':
        form = PagoForm(request.POST)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.cliente = cliente
            pago.organization = request.org
            pago.registrado_por = request.user
            pago.save()

            pagos = Pago.objects.filter(organization=request.org, cliente=cliente)
            response = render(request, 'cxc/_pagos_lista.html', {
                'pagos': pagos,
                'cliente': cliente,
            })
            response['HX-Trigger'] = 'closeModal'
            return response

        # Formulario con errores — retorna el modal con errores
        return render(request, 'cxc/_pago_form.html', {
            'form': form,
            'cliente': cliente,
        })

    # GET: retorna el formulario vacío
    form = PagoForm()
    return render(request, 'cxc/_pago_form.html', {
        'form': form,
        'cliente': cliente,
    })


@login_required
def aging_report(request):
    """
    Reporte de aging completo: todos los clientes con deuda desglosada por tramo.
    """
    clientes_qs = _clientes_con_deuda(request.org)

    filas = []
    totales = {
        't0_30': Decimal('0'),
        't31_60': Decimal('0'),
        't61_90': Decimal('0'),
        't90_mas': Decimal('0'),
        'total': Decimal('0'),
    }

    for cliente in clientes_qs:
        pedidos = Pedido.objects.filter(
            organization=request.org,
            cliente=cliente,
            estado__in=ESTADOS_ACTIVOS,
        )
        aging_cliente = {'t0_30': Decimal('0'), 't31_60': Decimal('0'), 't61_90': Decimal('0'), 't90_mas': Decimal('0')}
        for p in pedidos:
            tramo = _calcular_tramo_aging(p.fecha_pedido)
            aging_cliente[tramo] += p.total

        fila_total = sum(aging_cliente.values())

        filas.append({
            'cliente': cliente,
            'saldo': cliente.saldo,
            'aging': aging_cliente,
            'total': fila_total,
        })

        for tramo, monto in aging_cliente.items():
            totales[tramo] += monto
        totales['total'] += fila_total

    context = {
        'filas': filas,
        'totales': totales,
    }
    return render(request, 'cxc/aging.html', context)


@login_required
def aging_csv(request):
    """Exporta el aging report completo a CSV."""
    clientes_qs = _clientes_con_deuda(request.org)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="aging_cxc.csv"'
    response.write('\ufeff')  # BOM para Excel

    writer = csv.writer(response)
    writer.writerow(['Cliente', '0-30 días', '31-60 días', '61-90 días', '+90 días', 'Total'])

    for cliente in clientes_qs:
        pedidos = Pedido.objects.filter(
            organization=request.org,
            cliente=cliente,
            estado__in=ESTADOS_ACTIVOS,
        )
        aging_cliente = {'t0_30': Decimal('0'), 't31_60': Decimal('0'), 't61_90': Decimal('0'), 't90_mas': Decimal('0')}
        for p in pedidos:
            tramo = _calcular_tramo_aging(p.fecha_pedido)
            aging_cliente[tramo] += p.total

        fila_total = sum(aging_cliente.values())
        writer.writerow([
            cliente.nombre,
            aging_cliente['t0_30'],
            aging_cliente['t31_60'],
            aging_cliente['t61_90'],
            aging_cliente['t90_mas'],
            fila_total,
        ])

    return response
