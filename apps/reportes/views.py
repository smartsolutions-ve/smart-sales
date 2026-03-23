"""Vistas de reportes y analytics."""
import csv
from datetime import date, timedelta

from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from decimal import Decimal

from apps.accounts.decorators import role_required
from apps.pedidos.models import Pedido, Cliente
from apps.accounts.models import User


def _parse_fechas(request):
    """Extrae filtros de fecha desde GET params."""
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')
    fecha_filter = Q()
    if desde:
        fecha_filter &= Q(pedidos_vendedor__fecha_pedido__gte=desde)
    if hasta:
        fecha_filter &= Q(pedidos_vendedor__fecha_pedido__lte=hasta)
    return desde, hasta, fecha_filter


def _parse_fechas_cliente(request):
    """Extrae filtros de fecha para reportes de clientes."""
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')
    fecha_filter = Q()
    if desde:
        fecha_filter &= Q(pedido__fecha_pedido__gte=desde)
    if hasta:
        fecha_filter &= Q(pedido__fecha_pedido__lte=hasta)
    return desde, hasta, fecha_filter


def _get_vendedores_qs(request):
    desde, hasta, fecha_filter = _parse_fechas(request)
    base_filter = Q(pedidos_vendedor__organization=request.org) & ~Q(pedidos_vendedor__estado='Cancelado')
    if desde:
        base_filter &= Q(pedidos_vendedor__fecha_pedido__gte=desde)
    if hasta:
        base_filter &= Q(pedidos_vendedor__fecha_pedido__lte=hasta)

    entregados_filter = Q(pedidos_vendedor__organization=request.org, pedidos_vendedor__estado='Entregado')
    if desde:
        entregados_filter &= Q(pedidos_vendedor__fecha_pedido__gte=desde)
    if hasta:
        entregados_filter &= Q(pedidos_vendedor__fecha_pedido__lte=hasta)

    return (
        User.objects
        .filter(organization=request.org, role__in=['gerente', 'vendedor'], is_active=True)
        .annotate(
            total_vendido=Sum('pedidos_vendedor__total', filter=base_filter),
            cantidad_pedidos=Count('pedidos_vendedor', filter=base_filter),
            pedidos_entregados=Count('pedidos_vendedor', filter=entregados_filter),
        )
        .order_by('-total_vendido')
    ), desde, hasta


def _get_clientes_qs(request):
    desde, hasta, _ = _parse_fechas_cliente(request)
    base_filter = ~Q(pedido__estado='Cancelado')
    if desde:
        base_filter &= Q(pedido__fecha_pedido__gte=desde)
    if hasta:
        base_filter &= Q(pedido__fecha_pedido__lte=hasta)

    return (
        Cliente.objects
        .filter(organization=request.org)
        .annotate(
            total_compras=Sum('pedido__total', filter=base_filter),
            cantidad_pedidos=Count('pedido', filter=base_filter),
        )
        .order_by('-total_compras')
    ), desde, hasta


@login_required
@role_required('gerente', 'superadmin')
def vendedores(request):
    """Reporte de métricas por vendedor (RN-018)."""
    vendedores_qs, desde, hasta = _get_vendedores_qs(request)
    paginator = Paginator(vendedores_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {'vendedores': page_obj, 'page_obj': page_obj, 'desde': desde, 'hasta': hasta}
    return render(request, 'reportes/vendedores.html', context)


@login_required
@role_required('gerente', 'superadmin')
def vendedores_csv(request):
    """Exportar reporte de vendedores a CSV."""
    vendedores_qs, desde, hasta = _get_vendedores_qs(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reporte_vendedores.csv"'
    response.write('\ufeff')  # BOM para Excel

    writer = csv.writer(response)
    writer.writerow(['#', 'Vendedor', 'Email', 'Rol', 'Pedidos', 'Entregados', 'Total Vendido'])

    for i, v in enumerate(vendedores_qs, 1):
        writer.writerow([
            i,
            v.get_full_name() or v.username,
            v.email,
            v.get_role_display(),
            v.cantidad_pedidos or 0,
            v.pedidos_entregados or 0,
            v.total_vendido or 0,
        ])

    return response


@login_required
@role_required('gerente', 'superadmin')
def clientes(request):
    """Reporte de top clientes por monto acumulado (RN-019)."""
    clientes_qs, desde, hasta = _get_clientes_qs(request)
    paginator = Paginator(clientes_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {'clientes': page_obj, 'page_obj': page_obj, 'desde': desde, 'hasta': hasta}
    return render(request, 'reportes/clientes.html', context)


@login_required
@role_required('gerente', 'superadmin')
def clientes_csv(request):
    """Exportar reporte de clientes a CSV."""
    clientes_qs, desde, hasta = _get_clientes_qs(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reporte_clientes.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['#', 'Cliente', 'Contacto', 'Teléfono', 'Pedidos', 'Total Acumulado'])

    for i, c in enumerate(clientes_qs, 1):
        writer.writerow([
            i,
            c.nombre,
            c.contacto,
            c.telefono,
            c.cantidad_pedidos or 0,
            c.total_compras or 0,
        ])

    return response
